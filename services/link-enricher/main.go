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

	fmt.Println(env)

	// 	var wg sync.WaitGroup
	//
	// 	sem := make(chan struct{}, 5)
	//
	// 	for _, url := range urls {
	// 		wg.Add(1)
	// 		go func() {
	// 			defer wg.Done()
	// 			sem <- struct{}{}
	// 			defer func() { <-sem }()
	// 			status, title, err := fetch(url)
	// 			if err != nil {
	// 				fmt.Println("не смог:", err)
	// 				return
	// 			}
	// 			fmt.Println(status, title)
	// 		}()
	// 	}
	// 	wg.Wait()

	r := kafka.NewReader(kafka.ReaderConfig{
		Brokers: []string{env},
		Topic:   "entry.created",
		GroupID: "link-enricher",
	})
	defer r.Close()
	fmt.Println("[link-enricher] слушаю entry.created...")

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
		status, title, err := fetch(event.URL)
		if err != nil {
			fmt.Println("не смог:", event.URL, err)
			continue
		}
		fmt.Println(status, title)
	}
}
