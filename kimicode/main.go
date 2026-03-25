// https://go.dev/play/p/6a3pFWVvm60
package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"net/http"
	"sync"
	"time"
)

const maxBatchSize = 128

type Image struct {
	Res  chan Result
	Data []byte
}

type Result struct {
	Faces []Rect `json:"faces"`
}

type Rect struct {
	// omit fields
}

// FaceDetectInBatch is a singleton method, we use a mutex to simulate it.
var mu sync.Mutex

// FaceDetectInBatch is a mock function that simulates face detection on GPU
func FaceDetectInBatch(images []Image) []Result {
	mu.Lock()
	defer mu.Unlock()
	// Simulate processing time
	time.Sleep(100 * time.Millisecond)

	results := make([]Result, 0, len(images))
	for range images {
		results = append(results, Result{
			Faces: []Rect{{}, {}},
		})
	}
	return results
}

type Worker struct {
	exit bool
	q    chan Image
}

const N int = 100
const D time.Duration = 300 * time.Millisecond

func NewWorker() *Worker {
	w := &Worker{
		q: make(chan Image, 3*N),
	}
	return w
}

func (w *Worker) Start() {
	tk := time.NewTicker(10 * time.Millisecond) // 300ms
	defer tk.Stop()

	for {
		// 每轮
		imgs := make([]Image, 0, N)
		shouldCall := false
		// 收集 imgs
		for {
			select {
			case <-tk.C:
				shouldCall = true
			case img, ok := <-w.q:
				if !ok {
					shouldCall = true
				}
				// 收集
				if ok {
					imgs = append(imgs, img)
				}
				if len(imgs) >= N {
					shouldCall = true
				}
			}
			// 收集足够了
			if shouldCall {
				break
			}
		}
		// 调用并清空
		if shouldCall {
			results := FaceDetectInBatch(imgs)
			for i, res := range results {
				imgs[i].Res <- res
			}
			imgs = nil
			shouldCall = false
		}
	}
}

func (w *Worker) Add(img Image) error {
	if !w.exit {
		w.q <- img
	}
	return errors.New("closed")
}

func (w *Worker) Close() {
	w.exit = true
	close(w.q)
}

var globalWorker *Worker

func main() {
	globalWorker = NewWorker()
	go globalWorker.Start()
	defer globalWorker.Close()

	http.HandleFunc("/faces:detect", detectHandler)
	fmt.Println("Server is running on :8080")
	log.Fatal(http.ListenAndServe(":8080", nil))
}

// you may want interview candidate to finish this handler :)

func detectHandler(w http.ResponseWriter, r *http.Request) {
	data, _ := io.ReadAll(r.Body)
	img := Image{
		Data: data,
		//ID:   strconv.FormatInt(time.Now().UnixNano(), 10), // use a ID
		Res: make(chan Result, 1),
	}

	// send to worker
	_ = globalWorker.Add(img)

	// fetch result
	ctx, cancel := context.WithTimeout(r.Context(), 3*time.Second)
	defer cancel()
	select {
	case <-ctx.Done():
	case res := <-img.Res:
		// fetch result
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(res)
		return
	}
	// send error
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusInternalServerError)
	json.NewEncoder(w).Encode(map[string]any{})
}
