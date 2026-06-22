use rusqlite::{params, OptionalExtension};
use serde::{Deserialize, Serialize};
use crate::db::DbPool;

#[derive(Serialize, Deserialize, Clone)]
pub struct StationInfo {
    pub id: String,
    pub name: String,
    pub provincia: String,
    pub latitud: f64,
    pub longitud: f64,
    pub elevacion: f64,
    pub ch: f64,
    pub is_active: bool,
}

pub fn get_station_by_id(pool: &DbPool, station_id: &str) -> Result<Option<StationInfo>, String> {
    let conn = pool.get().map_err(|e| e.to_string())?;
    
    let sid = station_id.trim().to_uppercase();
    
    let mut stmt = conn.prepare(
        "SELECT id, name, provincia, latitud, longitud, elevacion, ch, is_active 
         FROM stations 
         WHERE id = ? OR id LIKE ?"
    ).map_err(|e| e.to_string())?;

    let like_sid = format!("%{}", sid);

    let station = stmt.query_row(
        params![sid, like_sid],
        |row| {
            Ok(StationInfo {
                id: row.get(0)?,
                name: row.get(1)?,
                provincia: row.get(2)?,
                latitud: row.get(3)?,
                longitud: row.get(4)?,
                elevacion: row.get(5)?,
                ch: row.get(6)?,
                is_active: row.get::<_, i32>(7)? == 1,
            })
        }
    ).optional().map_err(|e| e.to_string())?;

    Ok(station)
}

pub fn get_all_stations(pool: &DbPool) -> Result<Vec<StationInfo>, String> {
    let conn = pool.get().map_err(|e| e.to_string())?;
    
    let mut stmt = conn.prepare(
        "SELECT id, name, provincia, latitud, longitud, elevacion, ch, is_active 
         FROM stations"
    ).map_err(|e| e.to_string())?;

    let stations_iter = stmt.query_map([], |row| {
        Ok(StationInfo {
            id: row.get(0)?,
            name: row.get(1)?,
            provincia: row.get(2)?,
            latitud: row.get(3)?,
            longitud: row.get(4)?,
            elevacion: row.get(5)?,
            ch: row.get(6)?,
            is_active: row.get::<_, i32>(7)? == 1,
        })
    }).map_err(|e| e.to_string())?;

    let mut stations = Vec::new();
    for st in stations_iter {
        if let Ok(station) = st {
            stations.push(station);
        }
    }

    Ok(stations)
}

pub fn insert_station(pool: &DbPool, st: &StationInfo) -> Result<(), String> {
    let conn = pool.get().map_err(|e| e.to_string())?;
    conn.execute(
        "INSERT INTO stations (id, name, provincia, latitud, longitud, elevacion, ch, is_active) 
         VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        params![st.id, st.name, st.provincia, st.latitud, st.longitud, st.elevacion, st.ch, if st.is_active { 1 } else { 0 }],
    ).map_err(|e| e.to_string())?;
    Ok(())
}

pub fn update_station(pool: &DbPool, st: &StationInfo) -> Result<(), String> {
    let conn = pool.get().map_err(|e| e.to_string())?;
    conn.execute(
        "UPDATE stations SET name=?, provincia=?, latitud=?, longitud=?, elevacion=?, ch=?, is_active=? 
         WHERE id=?",
        params![st.name, st.provincia, st.latitud, st.longitud, st.elevacion, st.ch, if st.is_active { 1 } else { 0 }, st.id],
    ).map_err(|e| e.to_string())?;
    Ok(())
}

pub fn delete_station(pool: &DbPool, id: &str) -> Result<(), String> {
    let conn = pool.get().map_err(|e| e.to_string())?;
    conn.execute(
        "DELETE FROM stations WHERE id=?",
        params![id],
    ).map_err(|e| e.to_string())?;
    Ok(())
}
