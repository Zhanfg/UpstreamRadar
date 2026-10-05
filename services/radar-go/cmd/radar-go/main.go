package main

import (
	"encoding/json"
	"fmt"
	"io"
	"os"

	radar "github.com/Zhanfg/UpstreamRadar/services/radar-go"
)

type request struct {
	Command string `json:"command"`
	Budget int `json:"budget"`
	Config *radar.Config `json:"config"`
	Repositories []radar.RepositorySignal `json:"repositories"`
}

func main() {
	data,err:=io.ReadAll(os.Stdin)
	if err!=nil { fail(fmt.Errorf("read stdin: %w",err)) }
	if len(data)==0 { fail(fmt.Errorf("expected JSON input on stdin")) }

	var input request
	if err:=json.Unmarshal(data,&input);err!=nil { fail(fmt.Errorf("decode input: %w",err)) }
	config:=radar.DefaultConfig()
	if input.Config!=nil { config=*input.Config }
	scheduler,err:=radar.NewScheduler(config)
	if err!=nil { fail(err) }

	command:=input.Command
	if command=="" { command="score" }
	var output any
	switch command {
	case "score":
		candidates,err:=scheduler.Score(input.Repositories)
		if err!=nil { fail(err) }
		output=map[string]any{
			"version":"radar-go/0.1",
			"command":"score",
			"count":len(candidates),
			"candidates":candidates,
		}
	case "schedule":
		budget:=input.Budget
		if budget<=0 { budget=100 }
		schedule,err:=scheduler.Schedule(input.Repositories,budget)
		if err!=nil { fail(err) }
		output=map[string]any{
			"version":"radar-go/0.1",
			"command":"schedule",
			"schedule":schedule,
		}
	case "validate":
		for _,signal:=range input.Repositories {
			if err:=signal.Validate();err!=nil { fail(err) }
		}
		output=map[string]any{
			"version":"radar-go/0.1",
			"command":"validate",
			"repositories":len(input.Repositories),
			"status":"ok",
		}
	default:
		fail(fmt.Errorf("unknown command %q",command))
	}
	encoder:=json.NewEncoder(os.Stdout)
	encoder.SetIndent("","  ")
	if err:=encoder.Encode(output);err!=nil { fail(err) }
}

func fail(err error) {
	_ = json.NewEncoder(os.Stderr).Encode(map[string]string{"error":err.Error()})
	os.Exit(2)
}
