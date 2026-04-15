use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Deserialize)]
pub struct CliAutoCalcRequest {
    pub hora_actual: String,
    pub pres_est: Option<String>,
    pub p3: Option<String>,
    pub irixhv: Option<String>,
    pub nddff: Option<String>,
    pub nddff_anterior: Option<String>,
    pub seven_ww: Option<String>,
}

#[derive(Serialize)]
pub struct CliAutoCalcResponse {
    pub dif: String,
    pub visibilidad: String,
    pub tiempo_presente: String,
    pub error: String,
}

fn get_vis_code_to_meters() -> HashMap<String, String> {
    let mut map = HashMap::new();
    // Códigos 00-49 (valores literales)
    map.insert("00".to_string(), "000".to_string());
    map.insert("01".to_string(), "001".to_string());
    map.insert("02".to_string(), "002".to_string());
    map.insert("03".to_string(), "003".to_string());
    map.insert("04".to_string(), "004".to_string());
    map.insert("05".to_string(), "005".to_string());
    map.insert("06".to_string(), "006".to_string());
    map.insert("07".to_string(), "007".to_string());
    map.insert("08".to_string(), "008".to_string());
    map.insert("09".to_string(), "009".to_string());
    map.insert("10".to_string(), "010".to_string());
    map.insert("11".to_string(), "011".to_string());
    map.insert("12".to_string(), "012".to_string());
    map.insert("13".to_string(), "013".to_string());
    map.insert("14".to_string(), "014".to_string());
    map.insert("15".to_string(), "015".to_string());
    map.insert("16".to_string(), "016".to_string());
    map.insert("17".to_string(), "017".to_string());
    map.insert("18".to_string(), "018".to_string());
    map.insert("19".to_string(), "019".to_string());
    map.insert("20".to_string(), "020".to_string());
    map.insert("21".to_string(), "021".to_string());
    map.insert("22".to_string(), "022".to_string());
    map.insert("23".to_string(), "023".to_string());
    map.insert("24".to_string(), "024".to_string());
    map.insert("25".to_string(), "025".to_string());
    map.insert("26".to_string(), "026".to_string());
    map.insert("27".to_string(), "027".to_string());
    map.insert("28".to_string(), "028".to_string());
    map.insert("29".to_string(), "029".to_string());
    map.insert("30".to_string(), "030".to_string());
    map.insert("31".to_string(), "031".to_string());
    map.insert("32".to_string(), "032".to_string());
    map.insert("33".to_string(), "033".to_string());
    map.insert("34".to_string(), "034".to_string());
    map.insert("35".to_string(), "035".to_string());
    map.insert("36".to_string(), "036".to_string());
    map.insert("37".to_string(), "037".to_string());
    map.insert("38".to_string(), "038".to_string());
    map.insert("39".to_string(), "039".to_string());
    map.insert("40".to_string(), "040".to_string());
    map.insert("41".to_string(), "041".to_string());
    map.insert("42".to_string(), "042".to_string());
    map.insert("43".to_string(), "043".to_string());
    map.insert("44".to_string(), "044".to_string());
    map.insert("45".to_string(), "045".to_string());
    map.insert("46".to_string(), "046".to_string());
    map.insert("47".to_string(), "047".to_string());
    map.insert("48".to_string(), "048".to_string());
    map.insert("49".to_string(), "049".to_string());
    // Códigos especiales 56-80
    map.insert("56".to_string(), "060".to_string());
    map.insert("57".to_string(), "070".to_string());
    map.insert("58".to_string(), "080".to_string());
    map.insert("59".to_string(), "090".to_string());
    map.insert("60".to_string(), "100".to_string());
    map.insert("61".to_string(), "110".to_string());
    map.insert("62".to_string(), "120".to_string());
    map.insert("63".to_string(), "130".to_string());
    map.insert("64".to_string(), "140".to_string());
    map.insert("65".to_string(), "150".to_string());
    map.insert("66".to_string(), "160".to_string());
    map.insert("67".to_string(), "170".to_string());
    map.insert("68".to_string(), "180".to_string());
    map.insert("69".to_string(), "190".to_string());
    map.insert("70".to_string(), "200".to_string());
    map.insert("71".to_string(), "210".to_string());
    map.insert("72".to_string(), "220".to_string());
    map.insert("73".to_string(), "230".to_string());
    map.insert("74".to_string(), "240".to_string());
    map.insert("75".to_string(), "250".to_string());
    map.insert("76".to_string(), "260".to_string());
    map.insert("77".to_string(), "270".to_string());
    map.insert("78".to_string(), "280".to_string());
    map.insert("79".to_string(), "290".to_string());
    map.insert("80".to_string(), "300".to_string());
    map
}

#[tauri::command]
pub fn calculate_cli_autofill(data: CliAutoCalcRequest) -> CliAutoCalcResponse {
    let mut res = CliAutoCalcResponse {
        dif: String::new(),
        visibilidad: String::new(),
        tiempo_presente: String::new(),
        error: String::new(),
    };

    // 1. DIF = pres_est - p3 en formato 00.0
    if let Some(pe) = data.pres_est.as_ref().and_then(|s| s.parse::<f64>().ok()) {
        if let Some(p3) = data.p3.as_ref().and_then(|s| s.parse::<f64>().ok()) {
            let dif = pe - p3;
            res.dif = format!("{:04.1}", dif.abs());
        }
    }

    // 2. VISIBILIDAD: últimos 2 dígitos de IrIxHVV
    if let Some(irixhv) = &data.irixhv {
        if irixhv.len() >= 2 {
            let code = &irixhv[irixhv.len() - 2..];
            let table = get_vis_code_to_meters();
            if let Some(vis) = table.get(code) {
                res.visibilidad = vis.clone();
            }
        }
    }

    // 3. TIEMPO PRESENTE (ww)
    // Si 7wwW1W2 existe, usar 2do y 3er dígito
    // Si vacío, comparar PRIMER DÍGITO de Nddff actual vs Nddff de 3 horas antes
    if let Some(sww) = &data.seven_ww {
        if !sww.is_empty() && sww.len() >= 2 {
            res.tiempo_presente = sww[1..3].to_string();
        }
    } else if let (Some(nc), Some(np)) = (&data.nddff, &data.nddff_anterior) {
        if !nc.is_empty() && !np.is_empty() {
            // Comparar SOLO el PRIMER DÍGITO (cantidad de nubes)
            let curr = nc.chars().next().unwrap_or('0');
            let prev = np.chars().next().unwrap_or('0');
            res.tiempo_presente = if curr > prev {
                "01".to_string() // Aumentó
            } else if curr == prev {
                "02".to_string() // Igual
            } else {
                "03".to_string() // Decreció
            };
        }
    }

    res
}
