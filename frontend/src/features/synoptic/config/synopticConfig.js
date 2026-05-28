/**
 * Configuración de temas por hora para el formulario sinóptico
 * Escala de azules basada en altura del sol
 */

export const hourThemes = {
    "06Z": { // 02:00 AM - Noche profunda
        bgGradient: "from-slate-950 to-blue-950",
        accentColor: "#1e293b",
        textColor: "text-slate-200",
        localTime: "02:00 AM"
    },
    "09Z": { // 05:00 AM - Amanecer
        bgGradient: "from-blue-950 to-blue-900",
        accentColor: "#172554",
        textColor: "text-blue-100",
        localTime: "05:00 AM"
    },
    "12Z": { // 08:00 AM - Mañana
        bgGradient: "from-blue-800 to-blue-600",
        accentColor: "#1d4ed8",
        textColor: "text-white",
        localTime: "08:00 AM"
    },
    "15Z": { // 11:00 AM - Mediodía
        bgGradient: "from-blue-600 to-blue-500",
        accentColor: "#2563eb",
        textColor: "text-white",
        localTime: "11:00 AM"
    },
    "18Z": { // 02:00 PM - Pico del Sol
        bgGradient: "from-blue-600 to-blue-400",
        accentColor: "#3b82f6",
        textColor: "text-white",
        localTime: "02:00 PM"
    },
    "21Z": { // 05:00 PM - Tarde
        bgGradient: "from-blue-700 to-blue-600",
        accentColor: "#1d4ed8",
        textColor: "text-white",
        localTime: "05:00 PM"
    },
    "00Z": { // 08:00 PM - Anochecer
        bgGradient: "from-blue-900 to-blue-800",
        accentColor: "#1e3a8a",
        textColor: "text-blue-100",
        localTime: "08:00 PM"
    },
    "03Z": { // 11:00 PM - Noche
        bgGradient: "from-slate-900 to-blue-950",
        accentColor: "#0f172a",
        textColor: "text-slate-200",
        localTime: "11:00 PM"
    }
};

// Headers de la tabla meteorológica
export const meteoHeaders = {
    1: ["MiMi MjMj", "YYGG Iw", "IIiii", "Fecha"],
    3: ["Ir iX H VV", "N dd ff", "1sn T T T", "2sn Td Td Td", "4 P P P P", "5 a P P P", "7 ww W1 W2"],
    5: ["8Nh CL CM CH", "333", "0CS DL DM DH", "1sn Tx Tx Tx", "2sn Tn Tn Tn", "3E j j j", "5 EEEjE"],
    7: ["5n Fn Fn Fn", "56DL DM DH", "58/59 P24P24P24", "6 RRR tr", "7R24R24R24R24", "8NsChs hs", "8NsChs hs"],
    9: ["8NsChs hs", "8NsChs hs", "9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp"],
    11: ["9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp"],
    13: ["9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp"],
    15: ["9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp", "555", "29 UUU"]
};

// Placeholders de la tabla meteorológica
export const meteoPlaceholders = {
    2: ["AAXX", "", "78", ""],
    4: ["", "", "10", "20", "4", "5", "7"],
    6: ["8", "333", "0", "10", "20", "3///", ""],
    8: ["", "56", "5", "6", "7", "8", "8"],
    10: ["8", "8", "9", "9", "9", "9", "9"],
    12: ["9", "9", "9", "9", "9", "9", "9"],
    14: ["9", "9", "9", "9", "9", "9", "9"],
    16: ["9", "9", "9", "9", "9", "555", "29"]
};

// Estilos CSS reutilizables
export const styles = {
    tableHeader: "bg-slate-600 text-white font-semibold text-xs px-2 py-2 text-center",
    inputClass: "bg-white border border-slate-300 text-slate-800 text-sm px-2 py-2 rounded w-full focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none text-center",
    readonlyClass: "bg-white border border-slate-300 text-blue-600 font-bold text-sm px-2 py-2 rounded w-full text-center",
    constantClass: "bg-slate-200 border border-slate-400 text-slate-700 font-bold text-sm px-2 py-2 rounded w-full text-center",
    errorClass: "text-red-500 text-sm mt-2 text-center"
};

// Estilos de hoja de cálculo compartidos para CLI 3074, 4074 y 5074
export const spreadsheetStyles = {
    th: "border border-slate-700 bg-slate-800/90 text-white font-bold text-sm py-2 px-1 align-middle whitespace-nowrap overflow-hidden text-center",
    subTh: "border border-slate-600 bg-slate-700/80 text-white text-xs font-semibold py-1 px-1 text-center",
    tdBorder: "border-[1px] border-slate-200 p-0 m-0 h-[30px] overflow-hidden bg-white hover:bg-slate-50 transition-colors",
    tdHeader: "bg-slate-200 text-slate-800 font-bold text-xs p-2 border border-slate-300 text-left whitespace-nowrap",
    input: {
        sky: "w-full text-center bg-transparent border-none focus:outline-none focus:ring-1 focus:ring-sky-500 focus:bg-sky-100/50 text-slate-800 text-[13px] font-mono h-full py-1",
        emerald: "w-full text-center bg-transparent border-none focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:bg-emerald-100/50 text-slate-800 text-[13px] font-mono h-full py-1",
        rose: "w-full text-center bg-transparent border-none focus:outline-none focus:ring-1 focus:ring-rose-500 focus:bg-rose-100/50 text-slate-800 text-[13px] font-mono h-full py-1"
    }
};
