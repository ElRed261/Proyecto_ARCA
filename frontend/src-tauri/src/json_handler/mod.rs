pub mod utils;
pub mod synoptic;
pub mod cli;

// Re-exportar todos los comandos para mantener compatibilidad
pub use synoptic::{
    save_observation_json,
    get_observations_list,
    get_observation,
    get_station_date_range,
};

pub use cli::{
    save_cli3074_json,
    load_cli3074_json,
    save_cli4074_json,
    load_cli4074_json,
    save_cli5074_json,
    load_cli5074_json,
};
