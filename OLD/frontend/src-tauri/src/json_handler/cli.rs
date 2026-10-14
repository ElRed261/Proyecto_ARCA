// ponytail: canonical implementation lives in modules::cli — thin re-export for compat
pub use crate::modules::cli::{
    load_cli3074_json, load_cli3074_json_core, load_cli4074_json, load_cli4074_json_core,
    load_cli5074_json, load_cli5074_json_core, save_cli3074_json, save_cli4074_json,
    save_cli5074_json,
};
