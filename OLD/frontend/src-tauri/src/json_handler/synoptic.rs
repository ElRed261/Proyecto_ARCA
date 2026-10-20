// ponytail: canonical implementation lives in modules::synoptic
pub use crate::modules::synoptic::calculations::{
    calc_car, calc_dif, calc_tiempo_presente, format_dif, get_prev_hour,
    get_visibilidad_from_irixhv, to_frontend_name, to_synop_name,
};
pub use crate::modules::synoptic::storage::{
    get_observation, get_observation_core, get_station_date_range, save_observation_json,
    save_observation_json_core,
};
