use skopraed_museum::{SkopraedScheduler, RepositorySignal, SchedulerConfig};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::io::{self, Read};

#[derive(Debug, Deserialize)]
struct Input {
    #[serde(default)]
    command: Option<String>,
    #[serde(default)]
    budget: Option<u32>,
    #[serde(default)]
    config: Option<SchedulerConfig>,
    #[serde(default)]
    repositories: Vec<RepositorySignal>,
}

#[derive(Debug, Serialize)]
struct ErrorOutput {
    error: String,
}

fn read_input() -> Result<Input, String> {
    let mut text = String::new();
    io::stdin()
        .read_to_string(&mut text)
        .map_err(|error| format!("stdin: {error}"))?;
    if text.trim().is_empty() {
        return Err("expected JSON input on stdin".into());
    }
    serde_json::from_str(&text).map_err(|error| format!("invalid JSON: {error}"))
}

fn run(input: Input) -> Result<Value, String> {
    let scheduler = SkopraedScheduler::new(input.config.unwrap_or_default())?;
    let command = input.command.as_deref().unwrap_or("score");

    match command {
        "score" => {
            let candidates = scheduler.score(&input.repositories);
            Ok(json!({
                "version": "skopraed-rs/1.0",
                "command": "score",
                "count": candidates.len(),
                "candidates": candidates,
            }))
        }
        "schedule" => {
            let budget = input.budget.unwrap_or(100);
            let schedule = scheduler.schedule(&input.repositories, budget);
            Ok(json!({
                "version": "skopraed-rs/1.0",
                "command": "schedule",
                "schedule": schedule,
            }))
        }
        "validate" => Ok(json!({
            "version": "skopraed-rs/1.0",
            "command": "validate",
            "repositories": input.repositories.len(),
            "status": "ok",
        })),
        other => Err(format!(
            "unknown command {other:?}; expected score, schedule, or validate"
        )),
    }
}

fn main() {
    match read_input().and_then(run) {
        Ok(value) => {
            println!(
                "{}",
                serde_json::to_string_pretty(&value)
                    .expect("serializing known JSON value cannot fail")
            );
        }
        Err(error) => {
            let payload = ErrorOutput { error };
            eprintln!(
                "{}",
                serde_json::to_string(&payload)
                    .expect("serializing error output cannot fail")
            );
            std::process::exit(2);
        }
    }
}
