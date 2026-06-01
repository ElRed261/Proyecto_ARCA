use super::json_pipeline::{DailyKpis, DailyObservation};
use std::collections::HashMap;

fn safe_f64(val: Option<f64>) -> Option<f64> {
    val.filter(|v| v.is_finite())
}

fn round_half_up(val: f64, decimals: u32) -> f64 {
    let multiplier = 10f64.powi(decimals as i32);
    let sign = val.signum();
    ((val.abs() * multiplier + 0.5 + 1e-12).floor() * sign) / multiplier
}

fn mean_or_none(vals: &[Option<f64>]) -> Option<f64> {
    let valid: Vec<f64> = vals.iter().filter_map(|&v| safe_f64(v)).collect();
    if valid.is_empty() {
        return None;
    }
    let sum: f64 = valid.iter().sum();
    Some(sum / valid.len() as f64)
}

fn sum_or_none(vals: &[Option<f64>]) -> Option<f64> {
    let valid: Vec<f64> = vals.iter().filter_map(|&v| safe_f64(v)).collect();
    if valid.is_empty() {
        return None;
    }
    let sum: f64 = valid.iter().sum();
    Some(sum)
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
        Some(max_val)
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
        Some(min_val)
    } else {
        None
    }
}

fn degrees_to_cardinal(degrees: f64) -> String {
    if !(0.0..=360.0).contains(&degrees) {
        return "N/A".to_string();
    }
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
    let speed_vals: Vec<f64> = speeds.iter().filter_map(|&s| safe_f64(s)).collect();
    if speed_vals.is_empty() {
        return None;
    }
    let speed_mean = speed_vals.iter().sum::<f64>() / speed_vals.len() as f64;
    if speed_mean < 0.1 {
        return Some("CALMA".to_string());
    }

    let mut dir_order = Vec::new();
    let mut freqs = HashMap::new();
    
    for &d in dirs {
        if let Some(deg) = safe_f64(d) {
            let card = degrees_to_cardinal(deg);
            if card != "N/A" && card != "CALMA" {
                let count = freqs.entry(card.clone()).or_insert(0);
                if *count == 0 {
                    dir_order.push(card.clone());
                }
                *count += 1;
            }
        }
    }

    for card in &dir_order {
        if let Some(&count) = freqs.get(card) {
            if count >= 3 {
                return Some(card.clone());
            }
        }
    }

    Some("VRB".to_string())
}

pub fn process_day_data(obs: &DailyObservation) -> DailyKpis {
    let mut p_est = Vec::new();
    let mut p_nmm = Vec::new();
    let mut rocio = Vec::new();
    let mut t_vapor = Vec::new();
    let mut hr = Vec::new();
    let mut v_dir = Vec::new();
    let mut v_vel = Vec::new();

    let mut tmaxs = Vec::new();
    let mut tmins = Vec::new();
    
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

    let p_nmm_max = max_or_none(&p_nmm).map(|v| round_half_up(v, 1));
    let p_nmm_min = min_or_none(&p_nmm).map(|v| round_half_up(v, 1));
    let p_nmm_media = if let (Some(mx), Some(mn)) = (p_nmm_max, p_nmm_min) {
        Some(round_half_up((mx + mn) / 2.0, 1))
    } else {
        None
    };

    let p_est_media = mean_or_none(&p_est).map(|v| round_half_up(v, 1));

    let rocio_media = mean_or_none(&rocio).map(|v| round_half_up(v, 1));
    let t_vapor_media = mean_or_none(&t_vapor).map(|v| round_half_up(v, 1));

    let hr_media = mean_or_none(&hr).map(|v| round_half_up(v, 1));
    let hr_max = max_or_none(&hr).map(|v| round_half_up(v, 0));
    let hr_min = min_or_none(&hr).map(|v| round_half_up(v, 0));

    let viento_dir_moda = wind_direction_mode(&v_dir, &v_vel);
    
    let v_vel_kmh: Vec<Option<f64>> = v_vel.iter().map(|&v| v.map(|x| x * 3.6)).collect();
    let viento_vel_media = mean_or_none(&v_vel_kmh).map(|v| round_half_up(v, 1));
    let viento_recorrido = sum_or_none(&v_vel_kmh).map(|v| round_half_up(v, 1));

    let mut max_vel_ms = f64::MIN;
    let mut max_vel_idx: Option<usize> = None;
    for (i, &vel) in v_vel.iter().enumerate() {
        if let Some(v) = safe_f64(vel) {
            if v > max_vel_ms {
                max_vel_ms = v;
                max_vel_idx = Some(i);
            }
        }
    }

    let viento_max_dir = if let Some(idx) = max_vel_idx {
        let vel_max_kmh = max_vel_ms * 3.6;
        let vel_max_redondeada = round_half_up(vel_max_kmh, 1);
        let deg = v_dir.get(idx).copied().flatten();
        let dir_str = if let Some(d) = deg {
            degrees_to_cardinal(d)
        } else {
            "N/A".to_string()
        };
        let vel_str = format!("{:.1}", vel_max_redondeada).replace('.', ",");
        Some(format!("{} {}", dir_str, vel_str))
    } else {
        Some("N/A".to_string())
    };

    let (nub_dia_media, nub_tarde_media, nub_media) = if !nub_dia.is_empty() || !nub_tarde.is_empty() {
        let nub_dia_sum: f64 = nub_dia.iter().filter_map(|&v| safe_f64(v)).sum();
        let nub_dia_count_valid = nub_dia.iter().filter_map(|&v| safe_f64(v)).count();
        let nub_dia_val = if nub_dia_count_valid > 0 {
            Some(nub_dia_sum / 3.0)
        } else {
            None
        };

        let nub_tarde_sum: f64 = nub_tarde.iter().filter_map(|&v| safe_f64(v)).sum();
        let nub_tarde_count_valid = nub_tarde.iter().filter_map(|&v| safe_f64(v)).count();
        let nub_tarde_val = if nub_tarde_count_valid > 0 {
            Some(nub_tarde_sum / 3.0)
        } else {
            None
        };

        let nub_media_val = if let (Some(dia), Some(tarde)) = (nub_dia_val, nub_tarde_val) {
            Some((dia + tarde) / 2.0)
        } else {
            None
        };

        (
            nub_dia_val.map(|v| round_half_up(v, 1)),
            nub_tarde_val.map(|v| round_half_up(v, 1)),
            nub_media_val.map(|v| round_half_up(v, 1))
        )
    } else {
        let valid_nub_all: Vec<f64> = nub_all.iter().filter_map(|&v| safe_f64(v)).collect();
        if !valid_nub_all.is_empty() {
            let mean_val = valid_nub_all.iter().sum::<f64>() / valid_nub_all.len() as f64;
            let rounded = round_half_up(mean_val, 1);
            (Some(rounded), None, Some(rounded))
        } else {
            (None, None, None)
        }
    };

    let t_max = max_or_none(&tmaxs).map(|v| round_half_up(v, 1));
    let t_min = min_or_none(&tmins).map(|v| round_half_up(v, 1));
    let t_media = if let (Some(mx), Some(mn)) = (t_max, t_min) {
        Some(round_half_up((mx + mn) / 2.0, 1))
    } else {
        None
    };

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
        t_max,
        t_min,
        t_media,
        p_nmm_max,
        p_nmm_min,
        p_nmm_media,
        p_est_media,
        lluvia: obs.resumen_dia.pp,
        viento_dir_moda,
        viento_vel_media,
        viento_max_dir,
        viento_recorrido,
        nub_dia_media,
        nub_tarde_media,
        nub_media,
        hr_max,
        hr_min,
        hr_media,
        rocio_media,
        t_vapor_media,
    }
}
