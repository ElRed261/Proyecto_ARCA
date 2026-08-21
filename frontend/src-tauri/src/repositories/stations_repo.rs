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

fn station_from_row(row: &rusqlite::Row<'_>) -> rusqlite::Result<StationInfo> {
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

pub fn get_station_by_id(pool: &DbPool, station_id: &str) -> Result<Option<StationInfo>, String> {
    let conn = pool.get().map_err(|e| e.to_string())?;

    let sid = station_id.trim().to_uppercase();

    // 1. La coincidencia exacta gana siempre.
    let exact = conn
        .query_row(
            "SELECT id, name, provincia, latitud, longitud, elevacion, ch, is_active
             FROM stations
             WHERE id = ?1",
            params![sid],
            station_from_row,
        )
        .optional()
        .map_err(|e| e.to_string())?;
    if exact.is_some() {
        return Ok(exact);
    }

    // 2. Fallback parcial (sufijo): solo si hay UNA coincidencia la resolución
    // es determinística; con varias se devuelve error listando candidatos.
    let like_sid = format!("%{}", sid);
    let mut stmt = conn
        .prepare(
            "SELECT id, name, provincia, latitud, longitud, elevacion, ch, is_active
             FROM stations
             WHERE id LIKE ?1",
        )
        .map_err(|e| e.to_string())?;

    let matches: Vec<StationInfo> = stmt
        .query_map(params![like_sid], station_from_row)
        .map_err(|e| e.to_string())?
        .collect::<Result<Vec<_>, _>>()
        .map_err(|e| e.to_string())?;

    match matches.len() {
        0 => Ok(None),
        1 => Ok(matches.into_iter().next()),
        n => Err(format!(
            "'{}' coincide con {} estaciones ({}) — especifique el ID completo",
            sid,
            n,
            matches.iter().map(|s| s.id.as_str()).collect::<Vec<_>>().join(", ")
        )),
    }
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
    for station in stations_iter.flatten() {
        stations.push(station);
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
