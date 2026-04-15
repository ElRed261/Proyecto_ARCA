pub mod audit;
pub mod calculations;
pub mod cli_autofill;
pub mod db;
pub mod json_handler;
pub mod summary;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            calculations::get_stations,
            calculations::calculate_observations,
            cli_autofill::calculate_cli_autofill,
            json_handler::save_observation_json,
            json_handler::get_observations_list,
            json_handler::get_observation,
            json_handler::get_station_date_range,
            json_handler::save_cli3074_json,
            json_handler::load_cli3074_json,
            json_handler::save_cli4074_json,
            json_handler::load_cli4074_json,
            audit::get_audit_logs,
            audit::get_correction_requests,
            audit::create_correction_request,
            summary::get_monthly_summaries,
            summary::create_monthly_summary
        ])
        .setup(|app| {
            // Database init
            if let Err(err) = db::init_db(app.handle()) {
                eprintln!("Error initializing database: {}", err);
            }
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
