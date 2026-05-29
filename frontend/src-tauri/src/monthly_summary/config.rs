pub struct ExcelConfig {
    pub sheet_daily: &'static str,
    pub sheet_cloud_temp: &'static str,
    pub sheet_rain: &'static str,
    pub rain_cell: (u32, u32), // (row, col) 0-indexed: G37 -> col 6, row 36
    pub rows_8_observations: [usize; 8],
    pub rows_cloud_day: [usize; 3],
    pub rows_cloud_afternoon: [usize; 3],
    pub rows_4_temperatures: [usize; 4],
    
    pub col_presion_estacion: usize,
    pub col_presion_nmm: usize,
    pub col_punto_rocio: usize,
    pub col_tension_vapor: usize,
    pub col_humedad_relativa: usize,
    pub col_viento_direccion: usize,
    pub col_viento_velocidad: usize,
    pub col_nuvosidad: usize,
    pub col_temp_maxima: usize,
    pub col_temp_minima: usize,
}

pub fn get_default_config() -> ExcelConfig {
    ExcelConfig {
        sheet_daily: "3074",
        sheet_cloud_temp: "4074",
        sheet_rain: "1200Z",
        rain_cell: (36, 6), // G37 (0-indexed)
        // Note: the python config uses 1-indexed rows like [11, 14, ...].
        // We subtract 1 to get 0-indexed row numbers.
        rows_8_observations: [10, 13, 16, 19, 22, 25, 28, 31],
        rows_cloud_day: [13, 16, 19],
        rows_cloud_afternoon: [22, 25, 28],
        rows_4_temperatures: [10, 16, 22, 28],
        
        col_presion_estacion: 1, 
        col_presion_nmm: 2,
        col_punto_rocio: 8,
        col_tension_vapor: 9,
        col_humedad_relativa: 10,
        col_viento_direccion: 11,
        col_viento_velocidad: 12,
        col_nuvosidad: 1,
        col_temp_maxima: 21,
        col_temp_minima: 22,
    }
}
