#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde_json::Value;
use std::fs;
use std::sync::Mutex;
use tauri::api::process::{Command, CommandChild};
use tauri::Manager;

const API_BASE: &str = "http://127.0.0.1:18157";

struct SidecarChild(Mutex<Option<CommandChild>>);

#[tauri::command]
async fn invoke_api(path: String, body: String) -> Result<String, String> {
    let client = reqwest::Client::new();
    let url = format!("{}{}", API_BASE, path);
    let parsed_body: Value = serde_json::from_str(&body).unwrap_or(Value::Null);

    let response = client
        .post(&url)
        .header("Content-Type", "application/json")
        .json(&parsed_body)
        .send()
        .await
        .map_err(|e| format!("Request failed: {}", e))?;

    let status = response.status();
    let text = response
        .text()
        .await
        .map_err(|e| format!("Failed to read body: {}", e))?;

    if status.is_success() {
        Ok(text)
    } else {
        Err(format!("API error ({}): {}", status.as_u16(), text))
    }
}

#[tauri::command]
async fn get_api(path: String) -> Result<String, String> {
    let client = reqwest::Client::new();
    let url = format!("{}{}", API_BASE, path);

    let response = client
        .get(&url)
        .send()
        .await
        .map_err(|e| format!("Request failed: {}", e))?;

    let status = response.status();
    let text = response
        .text()
        .await
        .map_err(|e| format!("Failed to read body: {}", e))?;

    if status.is_success() {
        Ok(text)
    } else {
        Err(format!("API error ({}): {}", status.as_u16(), text))
    }
}

fn config_dir(app: &tauri::AppHandle) -> Result<std::path::PathBuf, String> {
    let dir = app
        .path_resolver()
        .app_config_dir()
        .ok_or_else(|| "Could not resolve config dir".to_string())?;
    fs::create_dir_all(&dir).map_err(|e| format!("Failed to create config dir: {}", e))?;
    Ok(dir)
}

#[tauri::command]
async fn set_api_key(app: tauri::AppHandle, service: String, key: String) -> Result<(), String> {
    let dir = config_dir(&app)?;
    let file = dir.join("api_keys.json");

    let mut keys: serde_json::Map<String, Value> = if file.exists() {
        let data =
            fs::read_to_string(&file).map_err(|e| format!("Failed to read config: {}", e))?;
        serde_json::from_str(&data).unwrap_or_default()
    } else {
        serde_json::Map::new()
    };

    keys.insert(service, Value::String(key));
    let serialized =
        serde_json::to_string_pretty(&keys).map_err(|e| format!("Serialization error: {}", e))?;
    fs::write(&file, serialized).map_err(|e| format!("Failed to write config: {}", e))?;
    Ok(())
}

#[tauri::command]
async fn get_api_key(app: tauri::AppHandle, service: String) -> Result<String, String> {
    let dir = config_dir(&app)?;
    let file = dir.join("api_keys.json");

    if !file.exists() {
        return Err(format!("No API key found for service: {}", service));
    }

    let data =
        fs::read_to_string(&file).map_err(|e| format!("Failed to read config: {}", e))?;
    let keys: serde_json::Map<String, Value> =
        serde_json::from_str(&data).map_err(|e| format!("Failed to parse config: {}", e))?;

    match keys.get(&service) {
        Some(Value::String(k)) => Ok(k.clone()),
        _ => Err(format!("No API key found for service: {}", service)),
    }
}

fn main() {
    tauri::Builder::default()
        .manage(SidecarChild(Mutex::new(None)))
        .setup(|app| {
            let (_, child) = Command::new_sidecar("textforge-server")
                .expect("failed to create sidecar command")
                .spawn()
                .expect("failed to spawn sidecar");

            let state = app.state::<SidecarChild>();
            *state.0.lock().unwrap() = Some(child);
            Ok(())
        })
        .on_window_event(|event| {
            if let tauri::WindowEvent::Destroyed = event.event() {
                let app = event.window().app_handle();
                let state = app.state::<SidecarChild>();
                let mut guard = state.0.lock().unwrap();
                if let Some(child) = guard.take() {
                    let _ = child.kill();
                }
            }
        })
        .invoke_handler(tauri::generate_handler![
            invoke_api,
            get_api,
            set_api_key,
            get_api_key
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
