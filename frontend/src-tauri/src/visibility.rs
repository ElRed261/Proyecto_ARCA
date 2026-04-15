// Tabla de visibilidad según OMM - Mapeo de códigos (XX) a visibilidad en metros
// Los últimos 2 dígitos del grupo IrIxHVV determinan la visibilidad

use std::collections::HashMap;

// Código de visibilidad (los 2 últimos dígitos de IrIxHVV) -> Visibilidad en metros
pub fn get_visibility_table() -> HashMap<&'static str, &'static str> {
    let mut table = HashMap::new();

    // Códigos de 00-49 (visibilidad en metros)
    table.insert("00", "0050"); // < 50m
    table.insert("01", "0100"); // 50m
    table.insert("02", "0200"); // 200m
    table.insert("03", "0300"); // 300m
    table.insert("04", "0400"); // 400m
    table.insert("05", "0500"); // 500m
    table.insert("06", "0600"); // 600m
    table.insert("07", "0700"); // 700m
    table.insert("08", "0800"); // 800m
    table.insert("09", "0900"); // 900m
    table.insert("10", "1000"); // 1km
    table.insert("11", "1100"); // 1.1km
    table.insert("12", "1200"); // 1.2km
    table.insert("13", "1300"); // 1.3km
    table.insert("14", "1400"); // 1.4km
    table.insert("15", "1500"); // 1.5km
    table.insert("16", "1600"); // 1.6km
    table.insert("17", "1700"); // 1.7km
    table.insert("18", "1800"); // 1.8km
    table.insert("19", "1900"); // 1.9km
    table.insert("20", "2000"); // 2km
    table.insert("21", "2100"); // 2.1km
    table.insert("22", "2200"); // 2.2km
    table.insert("23", "2300"); // 2.3km
    table.insert("24", "2400"); // 2.4km
    table.insert("25", "2500"); // 2.5km
    table.insert("26", "2600"); // 2.6km
    table.insert("27", "2700"); // 2.7km
    table.insert("28", "2800"); // 2.8km
    table.insert("29", "2900"); // 2.9km
    table.insert("30", "3000"); // 3km
    table.insert("31", "3100"); // 3.1km
    table.insert("32", "3200"); // 3.2km
    table.insert("33", "3300"); // 3.3km
    table.insert("34", "3400"); // 3.4km
    table.insert("35", "3500"); // 3.5km
    table.insert("36", "3600"); // 3.6km
    table.insert("37", "3700"); // 3.7km
    table.insert("38", "3800"); // 3.8km
    table.insert("39", "3900"); // 3.9km
    table.insert("40", "4000"); // 4km
    table.insert("41", "4100"); // 4.1km
    table.insert("42", "4200"); // 4.2km
    table.insert("43", "4300"); // 4.3km
    table.insert("44", "4400"); // 4.4km
    table.insert("45", "4500"); // 4.5km
    table.insert("46", "4600"); // 4.6km
    table.insert("47", "4700"); // 4.7km
    table.insert("48", "4800"); // 4.8km
    table.insert("49", "4900"); // 4.9km

    // Códigos especiales 56-80 (mayor.visibility)
    table.insert("56", "0600"); // 6km
    table.insert("57", "0700"); // 7km
    table.insert("58", "0800"); // 8km
    table.insert("59", "0900"); // 9km
    table.insert("60", "10000"); // 10km
    table.insert("61", "11000"); // 11km
    table.insert("62", "12000"); // 12km
    table.insert("63", "13000"); // 13km
    table.insert("64", "14000"); // 14km
    table.insert("65", "15000"); // 15km
    table.insert("66", "16000"); // 16km
    table.insert("67", "17000"); // 17km
    table.insert("68", "18000"); // 18km
    table.insert("69", "19000"); // 19km
    table.insert("70", "20000"); // 20km
    table.insert("71", "21000"); // 21km
    table.insert("72", "22000"); //  presente22km
    table.insert("73", "23000"); // 23km
    table.insert("74", "24000"); // 24km
    table.insert("75", "25000"); // 25km
    table.insert("76", "26000"); // 26km
    table.insert("77", "27000"); // 27km
    table.insert("78", "28000"); // 28km
    table.insert("79", "29000"); // 29km
    table.insert("80", "30000"); // 30km+

    table
}

// Obtener visibilidad desde los últimos 2 dígitos de IrIxHVV
// Si IrIxHVV = "32566", los últimos 2 dígitos son "66" -> retorna "16000" (16km)
pub fn get_visibility_from_irixhv(irixhv: &str) -> Option<String> {
    if irixhv.len() < 2 {
        return None;
    }

    let code = &irixhv[irixhv.len() - 2..];
    let table = get_visibility_table();

    table.get(code).map(|s| s.to_string())
}

// Calcular diferencia de presión en formato 00.0
// Ej: pres_est=1013.2, p3=1016.8 -> dif = -3.6 -> retorna "03.6"
pub fn calculate_pressure_diff(pres_est: f64, p3: f64) -> String {
    let dif = pres_est - p3;
    // Formato: signo (0/+) + valor con 1 decimal
    let formatted = if dif >= 0.0 {
        format!("{:04.1}", dif)
    } else {
        format!("{:04.1}", dif.abs())
    };
    formatted
}

// Calcular tiempo presente (ww) desde el segundo y tercer dígito de 7wwW1W2
// Si 7wwW1W2 está vacío, comparar Nddff actual vs Nddff anterior
// Si N actual > N anterior -> "01"
// Si N actual = N anterior -> "02"
// Si N actual < N anterior -> "03"
pub fn calculate_ww_from_comparison(n_current: &str, n_previous: &str) -> String {
    if n_current.is_empty() || n_previous.is_empty() {
        return String::new();
    }

    // Tomar solo el primer dígito de N (cantidad de nubes)
    let n_curr = n_current
        .chars()
        .next()
        .unwrap_or('0')
        .to_digit(10)
        .unwrap_or(0);
    let n_prev = n_previous
        .chars()
        .next()
        .unwrap_or('0')
        .to_digit(10)
        .unwrap_or(0);

    if n_curr > n_prev {
        "01".to_string()
    } else if n_curr == n_prev {
        "02".to_string()
    } else {
        "03".to_string()
    }
}
