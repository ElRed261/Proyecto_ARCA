pub mod audit;
pub mod auth;
pub mod calculations;
pub mod cli_autofill;
pub mod db;
pub mod json_handler;
pub mod summary;
pub mod monthly_summary;
pub mod app_config;
pub mod repositories;
pub mod infrastructure;
pub mod ports;
pub mod adapters;

use tauri::Manager;
#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .manage(auth::SessionStore::default())
        .invoke_handler(tauri::generate_handler![
            calculations::get_stations,
            calculations::create_station,
            calculations::update_station,
            calculations::delete_station,
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
            audit::commands::audit_browse_stations,
            audit::commands::audit_browse_years,
            audit::commands::audit_browse_months,
            audit::commands::audit_browse_days,
            audit::commands::audit_load_observation,
            audit::commands::audit_mark_error,
            audit::commands::audit_unmark_error,
            audit::commands::audit_update_error_mark_note,
            audit::commands::audit_propose_correction,
            audit::commands::audit_get_error_report,
            audit::commands::audit_export_corrected_json,
            audit::commands::audit_get_person_summary,
            summary::get_monthly_summaries,
            summary::create_monthly_summary,
            auth::login_user,
            auth::get_users,
            auth::update_user,
            auth::change_password,
            auth::delete_user,
            monthly_summary::commands::ms_load_station_month,
            monthly_summary::commands::ms_load_station_month_with_corrections,
            monthly_summary::commands::ms_generate_summary,
            monthly_summary::commands::ms_list_history,
            monthly_summary::commands::ms_load_summary,
            monthly_summary::commands::ms_export_excel,
            monthly_summary::commands::ms_delete_summary,
            app_config::get_app_config,
            app_config::set_app_config,
            app_config::get_assigned_station
        ])
        .setup(|app| {
            let pool = db::init_db(app.handle())
                .expect("FATAL: No se pudo inicializar la base de datos");
            app.manage(pool);
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
