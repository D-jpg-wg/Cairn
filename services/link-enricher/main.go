package main

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"regexp"
	// 	"sync"
	"github.com/segmentio/kafka-go"
	"time"
)

type EntryCreated struct {
	ID      string `json:"id"`
	OwnerID string `json:"owner_id"`
	Type    string `json:"type"`
	URL     string `json:"url"`
}

type LinkedEnriched struct {
	ID     string `json:"id"`
	URL    string `json:"url"`
	Status int    `json:"status"`
	Title  string `json:"title"`
}

func fetch(url string) (int, string, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return 0, "", err
	}
	resp, err := http.DefaultClient.Do(req)

	if err != nil {
		return 0, "", err
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)

	if err != nil {
		return 0, "", err
	}
	re := regexp.MustCompile("<title>(.*?)</title>")
	m := re.FindStringSubmatch(string(body))

	if len(m) == 0 {
		return resp.StatusCode, "", nil
	}

	return resp.StatusCode, m[1], nil
}

func main() {

	env := os.Getenv("KAFKA_BOOTSTRAP_SERVERS")
	if env == "" {
		env = "localhost:9092"
	}

	r := kafka.NewReader(kafka.ReaderConfig{
		Brokers: []string{env},
		Topic:   "entry.created",
		GroupID: "link-enricher",
	})
	defer r.Close()
	fmt.Println("[link-enricher] слушаю entry.created...")

	w := &kafka.Writer{
		Addr:                   kafka.TCP(env),
		Topic:                  "link.enriched",
		RequiredAcks:           kafka.RequireOne,
		BatchTimeout:           10 * time.Millisecond,
		AllowAutoTopicCreation: true,
	}
	defer w.Close()

	sem := make(chan struct{}, 5)

	for {
		msg, err := r.ReadMessage(context.Background())
		if err != nil {
			fmt.Println("ошибка чтения:", err)
			continue
		}
		var event EntryCreated

		if err := json.Unmarshal(msg.Value, &event); err != nil {
			fmt.Println("битый json:", err)
			continue
		}
		fmt.Printf("получил %+v\n", event)

		if event.URL == "" {
			continue
		}
		sem <- struct{}{}
		go func(event EntryCreated) {
			defer func() { <-sem }()
			status, title, err := fetch(event.URL)
			if err != nil {
				fmt.Println("не смог:", event.URL, err)
				return
			}
			payload, _ := json.Marshal(LinkedEnriched{
				ID:     event.ID,
				URL:    event.URL,
				Status: status,
				Title:  title,
			})
			wctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
			err = w.WriteMessages(wctx, kafka.Message{
				Key:   []byte(event.ID),
				Value: payload,
			})
			cancel()
			if err != nil {
				fmt.Println("не отправил:", event.ID, err)
				return
			}
		}(event)
	}
}
