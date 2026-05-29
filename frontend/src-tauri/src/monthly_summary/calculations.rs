use super::json_pipeline::{DailyKpis, DailyObservation};
use std::collections::HashMap;

fn safe_f64(val: Option<f64>) -> Option<f64> {
    val.filter(|v| v.is_finite())
}

fn mean_or_none(vals: &[Option<f64>]) -> Option<f64> {
    let valid: Vec<f64> = vals.iter().filter_map(|&v| safe_f64(v)).collect();
    if valid.is_empty() {
        return None;
    }
    let sum: f64 = valid.iter().sum();
    Some((sum / valid.len() as f64 * 10.0).round() / 10.0)
}

fn sum_or_none(vals: &[Option<f64>]) -> Option<f64> {
    let valid: Vec<f64> = vals.iter().filter_map(|&v| safe_f64(v)).collect();
    if valid.is_empty() {
        return None;
    }
    let sum: f64 = valid.iter().sum();
    Some((sum * 10.0).round() / 10.0)
}

fn max_or_none(vals: &[Option<f64>]) -> Option<f64> {
    let mut max_val = f64::NEG_INFINITY;
    let mut found = false;
    for &v in vals {
        if let Some(f) = safe_f64(v) {
            if f > max_val {
                max_val = f;
            }
            found = true;
        }
    }
    if found {
        Some((max_val * 10.0).round() / 10.0)
    } else {
        None
    }
}

fn min_or_none(vals: &[Option<f64>]) -> Option<f64> {
    let mut min_val = f64::INFINITY;
    let mut found = false;
    for &v in vals {
        if let Some(f) = safe_f64(v) {
            if f < min_val {
                min_val = f;
            }
            found = true;
        }
    }
    if found {
        Some((min_val * 10.0).round() / 10.0)
    } else {
        None
    }
}

fn degrees_to_cardinal(degrees: f64) -> String {
    if degrees == 0.0 {
        return "CALMA".to_string();
    }
    let dirs = [
        "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
        "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"
    ];
    let idx = ((degrees / 22.5).round() as usize) % 16;
    dirs[idx].to_string()
}

fn wind_direction_mode(dirs: &[Option<f64>], speeds: &[Option<f64>]) -> Option<String> {
    let mut speed_sum = 0.0;
    let mut count = 0;
    for &s in speeds {
        if let Some(f) = safe_f64(s) {
            speed_sum += f;
            count += 1;
        }
    }
    if count > 0 && speed_sum / (count as f64) < 0.1 {
        return Some("CALMA".to_string());
    }

    let mut freqs = HashMap::new();
    for &d in dirs {
        if let Some(deg) = safe_f64(d) {
            let card = degrees_to_cardinal(deg);
            *freqs.entry(card).or_insert(0) += 1;
        }
    }

    if freqs.is_empty() {
        return None;
    }

    let mut max_count = 0;
    let mut mode_dir = String::new();
    for (dir, c) in &freqs {
        if *c > max_count {
            max_count = *c;
            mode_dir = dir.clone();
        }
    }

    if max_count >= 3 {
        Some(mode_dir)
    } else {
        Some("VRB".to_string())
    }
}

pub fn process_day_data(obs: &DailyObservation) -> DailyKpis {
    // Collect 8-hourly observations
    let mut p_est = Vec::new();
    let mut p_nmm = Vec::new();
    let mut rocio = Vec::new();
    let mut t_vapor = Vec::new();
    let mut hr = Vec::new();
    let mut v_dir = Vec::new();
    let mut v_vel = Vec::new();

    // Collect temps
    let mut tmaxs = Vec::new();
    let mut tmins = Vec::new();
    
    // Collect clouds
    let mut nub_dia = Vec::new();
    let mut nub_tarde = Vec::new();
    let mut nub_all = Vec::new();

    for hr_rec in &obs.horarias {
        match hr_rec.hora.as_str() {
            "06Z" | "09Z" | "12Z" | "15Z" | "18Z" | "21Z" | "00Z" | "03Z" => {
                p_est.push(hr_rec.datos.p_est);
                p_nmm.push(hr_rec.datos.p_nmm);
                rocio.push(hr_rec.datos.rocio);
                t_vapor.push(hr_rec.datos.t_vapor);
                hr.push(hr_rec.datos.hr);
                v_dir.push(hr_rec.datos.v_dir_deg);
                v_vel.push(hr_rec.datos.v_vel);
                
                // If cloud is in hourly (for json fallback)
                if let Some(n) = hr_rec.datos.nub {
                    nub_all.push(Some(n));
                }
            }
            "TMAX" => tmaxs.push(hr_rec.datos.tmax),
            "TMIN" => tmins.push(hr_rec.datos.tmin),
            "filas_nuvosidad_dia" => {
                nub_dia.push(hr_rec.datos.nub);
                nub_all.push(hr_rec.datos.nub);
            }
            "filas_nuvosidad_tarde" => {
                nub_tarde.push(hr_rec.datos.nub);
                nub_all.push(hr_rec.datos.nub);
            }
            _ => {}
        }
    }

    let p_nmm_media = mean_or_none(&p_nmm);
    let p_nmm_max = max_or_none(&p_nmm);
    let p_nmm_min = min_or_none(&p_nmm);

    let p_est_media = mean_or_none(&p_est);
    let p_est_max = max_or_none(&p_est);
    let p_est_min = min_or_none(&p_est);

    let rocio_media = mean_or_none(&rocio);
    let t_vapor_media = mean_or_none(&t_vapor);

    let hr_media = mean_or_none(&hr);
    let hr_max = max_or_none(&hr).map(|v| v.round());
    let hr_min = min_or_none(&hr).map(|v| v.round());

    let viento_dir_moda = wind_direction_mode(&v_dir, &v_vel);
    
    // km/h conversion
    let v_vel_kmh: Vec<Option<f64>> = v_vel.iter().map(|&v| v.map(|x| x * 3.6)).collect();
    let viento_vel_media = mean_or_none(&v_vel_kmh);
    let viento_recorrido = sum_or_none(&v_vel_kmh);

    let mut max_vel = -1.0;
    let mut max_dir = None;
    for (i, &vel) in v_vel_kmh.iter().enumerate() {
        if let Some(v) = vel {
            if v > max_vel {
                max_vel = v;
                max_dir = v_dir.get(i).copied().flatten();
            }
        }
    }
    
    let viento_max_dir = if max_vel >= 0.0 {
        let max_vel_round = (max_vel * 10.0).round() / 10.0;
        let dir_str = if let Some(d) = max_dir { degrees_to_cardinal(d) } else { "N/A".to_string() };
        let vel_str = max_vel_round.to_string().replace('.', ",");
        Some(format!("{} {}", dir_str, vel_str))
    } else {
        None
    };

    let nub_dia_media = if nub_dia.is_empty() { mean_or_none(&nub_all) } else { mean_or_none(&nub_dia) };
    let nub_tarde_media = if nub_tarde.is_empty() { None } else { mean_or_none(&nub_tarde) };
    let nub_media = mean_or_none(&nub_all);

    let t_max = max_or_none(&tmaxs);
    let t_min = min_or_none(&tmins);
    let t_media = if let (Some(mx), Some(mn)) = (t_max, t_min) {
        Some(((mx + mn) / 2.0 * 10.0).round() / 10.0)
    } else {
        None
    };

    // YYYY-MM-DD from DDMMYYYY
    let dias = if obs.meta.fecha.len() == 8 {
        format!("{}-{}-{}", 
            &obs.meta.fecha[4..8], 
            &obs.meta.fecha[2..4], 
            &obs.meta.fecha[0..2])
    } else {
        obs.meta.fecha.clone()
    };

    DailyKpis {
        dias,
        p_est_media, p_est_max, p_est_min,
        p_nmm_media, p_nmm_max, p_nmm_min,
        rocio_media, t_vapor_media,
        hr_media, hr_max, hr_min,
        viento_dir_moda, viento_vel_media, viento_recorrido, viento_max_dir,
        nub_dia_media, nub_tarde_media, nub_media,
        t_obs1: None, t_obs2: None, t_obs3: None, t_obs4: None,
        t_max, t_min, t_media,
        lluvia: obs.resumen_dia.pp,
    }
}

