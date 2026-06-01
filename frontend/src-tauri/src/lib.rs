pub mod audit;
pub mod auth;
pub mod calculations;
pub mod cli_autofill;
pub mod db;
pub mod json_handler;
pub mod summary;
pub mod monthly_summary;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![
            calculations::get_stations,
            calculations::calculate_observations,
            cli_autofill::calculate_cli_autofill,
            json_handler::synoptic::save_observation_json,
            json_handler::synoptic::get_observations_list,
            json_handler::synoptic::get_observation,
            json_handler::synoptic::get_station_date_range,
            json_handler::cli::save_cli3074_json,
            json_handler::cli::load_cli3074_json,
            json_handler::cli::save_cli4074_json,
            json_handler::cli::load_cli4074_json,
            json_handler::cli::save_cli5074_json,
            json_handler::cli::load_cli5074_json,
            audit::get_audit_logs,
            audit::get_correction_requests,
            audit::create_correction_request,
            summary::get_monthly_summaries,
            summary::create_monthly_summary,
            auth::login_user,
            auth::get_users,
            auth::update_user,
            auth::change_password,
            auth::delete_user,
            monthly_summary::commands::ms_load_station_month,
            monthly_summary::commands::ms_generate_summary,
            monthly_summary::commands::ms_list_history,
            monthly_summary::commands::ms_load_summary,
            monthly_summary::commands::ms_export_excel,
            monthly_summary::commands::ms_delete_summary
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
