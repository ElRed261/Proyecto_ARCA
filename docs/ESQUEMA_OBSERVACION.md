# ESQUEMA DEL DOCUMENTO DE OBSERVACIÓN — v3 (CONGELADO)

> **Estado: congelado por el dueño (2026-10-26).** Este documento es el
> contrato de `schema_version = "ESQUEMA-NUEVO-v3"`. Cualquier herramienta
> (transformador de Excel, importador, UI, auditoría, resumen o IA) que escriba
> o lea observaciones tiene que respetarlo. Si este archivo y una
> implementación discrepan, **discrepa la implementación**.
>
> Copia legible para el dueño: `~/Documentos/OMS/pruebas/esquema-observacion-v3.json`
> Contrato máquina: `docs/esquema_observacion.json` (el mismo JSON, versión).

## Reglas del dueño (obligatorias)

1. **El esquema es el estándar.** Todo documento lleva SIEMPRE todas las claves,
   aunque no tengan dato. Lo que el Excel no trae queda **vacío** (`""`), nunca
   ausente y nunca inventado.
2. **Las ocho horas sinópticas siempre existen** (`06Z 09Z 12Z 15Z 18Z 21Z 00Z
   03Z`) con su estructura completa. Una hora sin observación es una hora con
   campos vacíos, **nunca `null`**.
3. En cada hora, las **24 claves `9spspsp_1.._24` y las 6
   `8NsChshs_1.._6` existen siempre**. Se llenan las que la observación usa y el
   resto queda vacío. Si hay grupos extra, se numeran en orden de aparición y el
   primero que toque rellena su clave (si se llena un 5.º 8Ns extra va a
   `8NsChshs_5`, no a otro).
4. **Solo entradas manuales se guardan.** Los valores calculados
   (presión NMM, humedad, punto de rocío, tensión de vapor, temperaturas
   derivadas) **no se almacenan**: el sistema los recalcula (regla R2 del dato).
5. **El procesamiento exige hojas Z.** Los Excel que no traen hojas Z NO se
   procesan (solo CLI, ni Z ni CLI: descartados con motivo). Con Z sin CLI,
   los tres bloques `cli` se escriben con sus estructuras vacías.
6. **La IA nunca borra datos**: si una celda del Excel no trae valor, esa clave
   del JSON queda vacía. Nunca se inventa un valor.
6. **Lecturas extremas** (Humedad maxima/minima): enteros. El promedio, un decimal.

## Estructura

```text
meta     : estacion, fecha (YYYY-MM-DD), actualizado (ISO con zona)
synop    : 8 horas × (observador + datos + grupos)
cli":
  "3074" : 24 horas × (viento_vel, pres_alti, fenomenos)
  "4074" : 24 horas × (observador)          ← solo iniciales
  "5074" : piche, tanque_c, evaporigrafo, subsuelo (7 prof. × f1/f2/f3),
           notas, iniciales_obs, iniciales_grupos (2/8/14/20),
           fenomenos[] (escalable)
```

### `synop.<hora>`

| Clave | Contenido | Ejemplo |
|---|---|---|
| `observador` | nombre completo del observador | `EMELYN MERCEDES` |
| `datos.ts` / `datos.th` | termómetro seco / húmedo | `25.9` / `25.4` |
| `datos.pres_est`, `p3`, `p24` | presión de estación, 3 h y 24 h | `1011.8` |
| `datos.Tmax`, `Tmin`, `Tmax_24h`, `Tmin_24h` | extremas | `27.4` |
| `datos.LL`, `datos.LL_24h` | lluvia | `0.0` |
| `grupos.YYGGiw … 7R24R24R24R24` | los grupos FM 12 verbatim | `01061` |
| `grupos.8NsChshs_1.._6` | grupos de nubes | `82816` |
| `grupos.9spspsp_1.._24` | carriles 9Sp | `90094` |

**Valores derivados prohibidos aquí**: `pres_nmm`, `hum_*`, `rocio`, `vapor`,
`visibilidad`. Se recalculan desde `ts`/`th`/`pres_est`/`p3`/`p24`.

### `cli["3074"]` — 24 horas, SOLO entradas manuales

| Clave | Contenido |
|---|---|
| `viento_vel` | velocidad del viento (entrada manual, m/s) |
| `pres_alti` | altímetro |
| `fenomenos.tiempo_presente` | código ww |
| `fenomenos.granizo / ventarron / neblina / trueno / relampago / rocio / polvo / calima / niebla / tornado` | booleanos (10 disponibles para todos los fenómenos del formulario) |

Nada derivado del synop se guarda aquí.

### `cli["4074"]` — 24 horas, SOLO iniciales

```text
"4074": { h: {"observador": "…"} for h 1..24 }
```

La nubosidad, las temperaturas extremas y las nubes bajas se derivan del
`synop`. El tipo **9 (Cumulonimbus) no se guarda**: el programa lo calcula
cuando el **tercer dígito** del grupo 8Ns es `9` (p. ej. `92816` → CB).

### `cli["5074"]` — entrada manual casi completa

| Clave | Contenido |
|---|---|
| `piche` | mm (valor único del día) |
| `tanque_c` | mm (valor único del día) |
| `evaporigrafo` | mm (valor único del día) |
| `subsuelo."5".."100"` | 7 profundidades (cm) × **3 filas** del formulario (`f1 f2 f3`) |
| `notas` | la nota del formulario (solo vive aquí) |
| `iniciales_obs` | las iniciales grandes del formulario |
| `iniciales_grupos."2"."8"."14"."20"` | las iniciales del rango AP17:AW18 |
| `fenomenos[]` | **lista escalable** — de 0 a N fenómenos del día |

**No se guardan presiones del 5074** (lect_bar, term_anexo, correc_temp,
pres_est, p_nmm): salen de la observación sinóptica del día.

Cada elemento de `fenomenos[]`:

```text
hora (hh:mm, la hora y el minuto vienen en DOS columnas del Excel y se unen),
raf_dir (dd), raf_vel (ff m/s), intensidad, fenomeno (código tipo RA/TS/DZ/V),
inicio, final, duracion, iniciales
```

## Ejemplo completo (contrato de prueba)

Este es el JSON canónico; **el transformador tiene que ser capaz de producir
exactamente esta forma** a partir de un Excel válido:

```json
{
 "schema_version": "ESQUEMA-NUEVO-v3",
 "meta": {
  "estacion": "78485",
  "fecha": "2025-10-01",
  "actualizado": "2026-10-26T13:00:00-04:00"
 },
 "synop": {
  "06Z": {
   "observador": "EMELYN MERCEDES",
   "datos": {
    "ts": "25.9",
    "th": "25.4",
    "pres_est": "1011.8",
    "p3": "1012.7",
    "p24": "1012.7",
    "Tmax": "27.4",
    "Tmin": "25.4",
    "Tmax_24h": "",
    "Tmin_24h": "",
    "LL": "0.0",
    "LL_24h": ""
   },
   "grupos": {
    "YYGGiw": "01061",
    "IrIXHVV": "32466",
    "Nddff": "21602",
    "7wwW1W2": "70601",
    "8NhCLCMCH": "82816",
    "0CSDLDMDH": "02000",
    "1snTxTxTx": "10259",
    "2snTnTnTn": "20252",
    "3Ejjj": "30///",
    "5EEEjE": "",
    "5nFnFnFn": "",
    "56DLDMDH": "02000",
    "6RRRtr": "",
    "7R24R24R24R24": "7",
    "8NsChshs_1": "82816",
    "8NsChshs_2": "82800",
    "8NsChshs_3": "81200",
    "8NsChshs_4": "82000",
    "8NsChshs_5": "",
    "8NsChshs_6": "",
    "9spspsp_1": "90094",
    "9spspsp_2": "94080",
    "9spspsp_3": "94320",
    "9spspsp_4": "94428",
    "9spspsp_5": "98264",
    "9spspsp_6": "98464",
    "9spspsp_7": "98664",
    "9spspsp_8": "98864",
    "9spspsp_9": "",
    "9spspsp_10": "",
    "9spspsp_11": "",
    "9spspsp_12": "",
    "9spspsp_13": "",
    "9spspsp_14": "",
    "9spspsp_15": "",
    "9spspsp_16": "",
    "9spspsp_17": "",
    "9spspsp_18": "",
    "9spspsp_19": "",
    "9spspsp_20": "",
    "9spspsp_21": "",
    "9spspsp_22": "",
    "9spspsp_23": "",
    "9spspsp_24": ""
   }
  },
  "12Z": {
   "observador": "PEDRO RUIZ",
   "datos": {
    "ts": "29.8",
    "th": "25.1",
    "pres_est": "1012.9",
    "p3": "1011.8",
    "p24": "",
    "Tmax": "31.0",
    "Tmin": "",
    "Tmax_24h": "",
    "Tmin_24h": "",
    "LL": "2.0",
    "LL_24h": ""
   },
   "grupos": {
    "YYGGiw": "02121",
    "IrIXHVV": "32466",
    "Nddff": "21602",
    "7wwW1W2": "170916",
    "8NhCLCMCH": "82816",
    "0CSDLDMDH": "02000",
    "1snTxTxTx": "10305",
    "2snTnTnTn": "20235",
    "3Ejjj": "30///",
    "5EEEjE": "",
    "5nFnFnFn": "",
    "56DLDMDH": "02000",
    "6RRRtr": "60112",
    "7R24R24R24R24": "7",
    "8NsChshs_1": "92816",
    "8NsChshs_2": "82800",
    "8NsChshs_3": "",
    "8NsChshs_4": "",
    "8NsChshs_5": "",
    "8NsChshs_6": "",
    "9spspsp_1": "91023",
    "9spspsp_2": "92500",
    "9spspsp_3": "93000",
    "9spspsp_4": "93500",
    "9spspsp_5": "94000",
    "9spspsp_6": "94500",
    "9spspsp_7": "95000",
    "9spspsp_8": "95500",
    "9spspsp_9": "",
    "9spspsp_10": "",
    "9spspsp_11": "",
    "9spspsp_12": "",
    "9spspsp_13": "",
    "9spspsp_14": "",
    "9spspsp_15": "",
    "9spspsp_16": "",
    "9spspsp_17": "",
    "9spspsp_18": "",
    "9spspsp_19": "",
    "9spspsp_20": "",
    "9spspsp_21": "",
    "9spspsp_22": "",
    "9spspsp_23": "",
    "9spspsp_24": ""
   }
  },
  "09Z": {
   "observador": "",
   "datos": {
    "ts": "",
    "th": "",
    "pres_est": "",
    "p3": "",
    "p24": "",
    "Tmax": "",
    "Tmin": "",
    "Tmax_24h": "",
    "Tmin_24h": "",
    "LL": "",
    "LL_24h": ""
   },
   "grupos": {
    "YYGGiw": "",
    "IrIXHVV": "",
    "Nddff": "",
    "7wwW1W2": "",
    "8NhCLCMCH": "",
    "0CSDLDMDH": "",
    "1snTxTxTx": "",
    "2snTnTnTn": "",
    "3Ejjj": "",
    "5EEEjE": "",
    "5nFnFnFn": "",
    "56DLDMDH": "",
    "6RRRtr": "",
    "7R24R24R24R24": "",
    "8NsChshs_1": "",
    "8NsChshs_2": "",
    "8NsChshs_3": "",
    "8NsChshs_4": "",
    "8NsChshs_5": "",
    "8NsChshs_6": "",
    "9spspsp_1": "",
    "9spspsp_2": "",
    "9spspsp_3": "",
    "9spspsp_4": "",
    "9spspsp_5": "",
    "9spspsp_6": "",
    "9spspsp_7": "",
    "9spspsp_8": "",
    "9spspsp_9": "",
    "9spspsp_10": "",
    "9spspsp_11": "",
    "9spspsp_12": "",
    "9spspsp_13": "",
    "9spspsp_14": "",
    "9spspsp_15": "",
    "9spspsp_16": "",
    "9spspsp_17": "",
    "9spspsp_18": "",
    "9spspsp_19": "",
    "9spspsp_20": "",
    "9spspsp_21": "",
    "9spspsp_22": "",
    "9spspsp_23": "",
    "9spspsp_24": ""
   }
  },
  "15Z": {
   "observador": "",
   "datos": {
    "ts": "",
    "th": "",
    "pres_est": "",
    "p3": "",
    "p24": "",
    "Tmax": "",
    "Tmin": "",
    "Tmax_24h": "",
    "Tmin_24h": "",
    "LL": "",
    "LL_24h": ""
   },
   "grupos": {
    "YYGGiw": "",
    "IrIXHVV": "",
    "Nddff": "",
    "7wwW1W2": "",
    "8NhCLCMCH": "",
    "0CSDLDMDH": "",
    "1snTxTxTx": "",
    "2snTnTnTn": "",
    "3Ejjj": "",
    "5EEEjE": "",
    "5nFnFnFn": "",
    "56DLDMDH": "",
    "6RRRtr": "",
    "7R24R24R24R24": "",
    "8NsChshs_1": "",
    "8NsChshs_2": "",
    "8NsChshs_3": "",
    "8NsChshs_4": "",
    "8NsChshs_5": "",
    "8NsChshs_6": "",
    "9spspsp_1": "",
    "9spspsp_2": "",
    "9spspsp_3": "",
    "9spspsp_4": "",
    "9spspsp_5": "",
    "9spspsp_6": "",
    "9spspsp_7": "",
    "9spspsp_8": "",
    "9spspsp_9": "",
    "9spspsp_10": "",
    "9spspsp_11": "",
    "9spspsp_12": "",
    "9spspsp_13": "",
    "9spspsp_14": "",
    "9spspsp_15": "",
    "9spspsp_16": "",
    "9spspsp_17": "",
    "9spspsp_18": "",
    "9spspsp_19": "",
    "9spspsp_20": "",
    "9spspsp_21": "",
    "9spspsp_22": "",
    "9spspsp_23": "",
    "9spspsp_24": ""
   }
  },
  "18Z": {
   "observador": "",
   "datos": {
    "ts": "",
    "th": "",
    "pres_est": "",
    "p3": "",
    "p24": "",
    "Tmax": "",
    "Tmin": "",
    "Tmax_24h": "",
    "Tmin_24h": "",
    "LL": "",
    "LL_24h": ""
   },
   "grupos": {
    "YYGGiw": "",
    "IrIXHVV": "",
    "Nddff": "",
    "7wwW1W2": "",
    "8NhCLCMCH": "",
    "0CSDLDMDH": "",
    "1snTxTxTx": "",
    "2snTnTnTn": "",
    "3Ejjj": "",
    "5EEEjE": "",
    "5nFnFnFn": "",
    "56DLDMDH": "",
    "6RRRtr": "",
    "7R24R24R24R24": "",
    "8NsChshs_1": "",
    "8NsChshs_2": "",
    "8NsChshs_3": "",
    "8NsChshs_4": "",
    "8NsChshs_5": "",
    "8NsChshs_6": "",
    "9spspsp_1": "",
    "9spspsp_2": "",
    "9spspsp_3": "",
    "9spspsp_4": "",
    "9spspsp_5": "",
    "9spspsp_6": "",
    "9spspsp_7": "",
    "9spspsp_8": "",
    "9spspsp_9": "",
    "9spspsp_10": "",
    "9spspsp_11": "",
    "9spspsp_12": "",
    "9spspsp_13": "",
    "9spspsp_14": "",
    "9spspsp_15": "",
    "9spspsp_16": "",
    "9spspsp_17": "",
    "9spspsp_18": "",
    "9spspsp_19": "",
    "9spspsp_20": "",
    "9spspsp_21": "",
    "9spspsp_22": "",
    "9spspsp_23": "",
    "9spspsp_24": ""
   }
  },
  "21Z": {
   "observador": "",
   "datos": {
    "ts": "",
    "th": "",
    "pres_est": "",
    "p3": "",
    "p24": "",
    "Tmax": "",
    "Tmin": "",
    "Tmax_24h": "",
    "Tmin_24h": "",
    "LL": "",
    "LL_24h": ""
   },
   "grupos": {
    "YYGGiw": "",
    "IrIXHVV": "",
    "Nddff": "",
    "7wwW1W2": "",
    "8NhCLCMCH": "",
    "0CSDLDMDH": "",
    "1snTxTxTx": "",
    "2snTnTnTn": "",
    "3Ejjj": "",
    "5EEEjE": "",
    "5nFnFnFn": "",
    "56DLDMDH": "",
    "6RRRtr": "",
    "7R24R24R24R24": "",
    "8NsChshs_1": "",
    "8NsChshs_2": "",
    "8NsChshs_3": "",
    "8NsChshs_4": "",
    "8NsChshs_5": "",
    "8NsChshs_6": "",
    "9spspsp_1": "",
    "9spspsp_2": "",
    "9spspsp_3": "",
    "9spspsp_4": "",
    "9spspsp_5": "",
    "9spspsp_6": "",
    "9spspsp_7": "",
    "9spspsp_8": "",
    "9spspsp_9": "",
    "9spspsp_10": "",
    "9spspsp_11": "",
    "9spspsp_12": "",
    "9spspsp_13": "",
    "9spspsp_14": "",
    "9spspsp_15": "",
    "9spspsp_16": "",
    "9spspsp_17": "",
    "9spspsp_18": "",
    "9spspsp_19": "",
    "9spspsp_20": "",
    "9spspsp_21": "",
    "9spspsp_22": "",
    "9spspsp_23": "",
    "9spspsp_24": ""
   }
  },
  "00Z": {
   "observador": "",
   "datos": {
    "ts": "",
    "th": "",
    "pres_est": "",
    "p3": "",
    "p24": "",
    "Tmax": "",
    "Tmin": "",
    "Tmax_24h": "",
    "Tmin_24h": "",
    "LL": "",
    "LL_24h": ""
   },
   "grupos": {
    "YYGGiw": "",
    "IrIXHVV": "",
    "Nddff": "",
    "7wwW1W2": "",
    "8NhCLCMCH": "",
    "0CSDLDMDH": "",
    "1snTxTxTx": "",
    "2snTnTnTn": "",
    "3Ejjj": "",
    "5EEEjE": "",
    "5nFnFnFn": "",
    "56DLDMDH": "",
    "6RRRtr": "",
    "7R24R24R24R24": "",
    "8NsChshs_1": "",
    "8NsChshs_2": "",
    "8NsChshs_3": "",
    "8NsChshs_4": "",
    "8NsChshs_5": "",
    "8NsChshs_6": "",
    "9spspsp_1": "",
    "9spspsp_2": "",
    "9spspsp_3": "",
    "9spspsp_4": "",
    "9spspsp_5": "",
    "9spspsp_6": "",
    "9spspsp_7": "",
    "9spspsp_8": "",
    "9spspsp_9": "",
    "9spspsp_10": "",
    "9spspsp_11": "",
    "9spspsp_12": "",
    "9spspsp_13": "",
    "9spspsp_14": "",
    "9spspsp_15": "",
    "9spspsp_16": "",
    "9spspsp_17": "",
    "9spspsp_18": "",
    "9spspsp_19": "",
    "9spspsp_20": "",
    "9spspsp_21": "",
    "9spspsp_22": "",
    "9spspsp_23": "",
    "9spspsp_24": ""
   }
  },
  "03Z": {
   "observador": "",
   "datos": {
    "ts": "",
    "th": "",
    "pres_est": "",
    "p3": "",
    "p24": "",
    "Tmax": "",
    "Tmin": "",
    "Tmax_24h": "",
    "Tmin_24h": "",
    "LL": "",
    "LL_24h": ""
   },
   "grupos": {
    "YYGGiw": "",
    "IrIXHVV": "",
    "Nddff": "",
    "7wwW1W2": "",
    "8NhCLCMCH": "",
    "0CSDLDMDH": "",
    "1snTxTxTx": "",
    "2snTnTnTn": "",
    "3Ejjj": "",
    "5EEEjE": "",
    "5nFnFnFn": "",
    "56DLDMDH": "",
    "6RRRtr": "",
    "7R24R24R24R24": "",
    "8NsChshs_1": "",
    "8NsChshs_2": "",
    "8NsChshs_3": "",
    "8NsChshs_4": "",
    "8NsChshs_5": "",
    "8NsChshs_6": "",
    "9spspsp_1": "",
    "9spspsp_2": "",
    "9spspsp_3": "",
    "9spspsp_4": "",
    "9spspsp_5": "",
    "9spspsp_6": "",
    "9spspsp_7": "",
    "9spspsp_8": "",
    "9spspsp_9": "",
    "9spspsp_10": "",
    "9spspsp_11": "",
    "9spspsp_12": "",
    "9spspsp_13": "",
    "9spspsp_14": "",
    "9spspsp_15": "",
    "9spspsp_16": "",
    "9spspsp_17": "",
    "9spspsp_18": "",
    "9spspsp_19": "",
    "9spspsp_20": "",
    "9spspsp_21": "",
    "9spspsp_22": "",
    "9spspsp_23": "",
    "9spspsp_24": ""
   }
  }
 },
 "cli": {
  "3074": {
   "2": {
    "viento_vel": "2.1",
    "pres_alti": "1013.2",
    "fenomenos": {
     "tiempo_presente": "06",
     "granizo": false,
     "ventarron": false,
     "neblina": false,
     "trueno": false,
     "relampago": false,
     "rocio": false,
     "polvo": false,
     "calima": false,
     "niebla": false,
     "tornado": false
    }
   },
   "3": {
    "viento_vel": "",
    "pres_alti": "",
    "fenomenos": {
     "tiempo_presente": "",
     "granizo": false,
     "ventarron": false,
     "neblina": false,
     "trueno": false,
     "relampago": false,
     "rocio": false,
     "polvo": false,
     "calima": false,
     "niebla": false,
     "tornado": false
    }
   },
   "5": {
    "viento_vel": "2.1",
    "pres_alti": "1014.3",
    "fenomenos": {
     "tiempo_presente": "15",
     "granizo": false,
     "ventarron": false,
     "neblina": false,
     "trueno": false,
     "relampago": false,
     "rocio": false,
     "polvo": false,
     "calima": false,
     "niebla": false,
     "tornado": false
    }
   },
   "8": {
    "viento_vel": "0.0",
    "pres_alti": "1014.3",
    "fenomenos": {
     "tiempo_presente": "06",
     "granizo": false,
     "ventarron": false,
     "neblina": false,
     "trueno": false,
     "relampago": false,
     "rocio": false,
     "polvo": false,
     "calima": false,
     "niebla": false,
     "tornado": false
    }
   },
   "11": {
    "viento_vel": "3.1",
    "pres_alti": "1015.1",
    "fenomenos": {
     "tiempo_presente": "",
     "granizo": false,
     "ventarron": false,
     "neblina": false,
     "trueno": false,
     "relampago": false,
     "rocio": false,
     "polvo": false,
     "calima": false,
     "niebla": false,
     "tornado": false
    }
   },
   "14": {
    "viento_vel": "4.1",
    "pres_alti": "1013.6",
    "fenomenos": {
     "tiempo_presente": "",
     "granizo": false,
     "ventarron": false,
     "neblina": false,
     "trueno": false,
     "relampago": false,
     "rocio": false,
     "polvo": false,
     "calima": false,
     "niebla": false,
     "tornado": false
    }
   },
   "17": {
    "viento_vel": "2.2",
    "pres_alti": "1013.0",
    "fenomenos": {
     "tiempo_presente": "",
     "granizo": false,
     "ventarron": false,
     "neblina": false,
     "trueno": false,
     "relampago": false,
     "rocio": false,
     "polvo": false,
     "calima": false,
     "niebla": false,
     "tornado": false
    }
   },
   "20": {
    "viento_vel": "2.1",
    "pres_alti": "1013.0",
    "fenomenos": {
     "tiempo_presente": "",
     "granizo": false,
     "ventarron": false,
     "neblina": false,
     "trueno": false,
     "relampago": false,
     "rocio": false,
     "polvo": false,
     "calima": false,
     "niebla": false,
     "tornado": false
    }
   },
   "23": {
    "viento_vel": "0.0",
    "pres_alti": "1013.0",
    "fenomenos": {
     "tiempo_presente": "",
     "granizo": false,
     "ventarron": false,
     "neblina": false,
     "trueno": false,
     "relampago": false,
     "rocio": false,
     "polvo": false,
     "calima": false,
     "niebla": false,
     "tornado": false
    }
   }
  },
  "4074": {
   "2": {
    "observador": "EMM"
   },
   "5": {
    "observador": "EMM"
   },
   "8": {
    "observador": "PR"
   },
   "11": {
    "observador": "PR"
   },
   "14": {
    "observador": ""
   },
   "17": {
    "observador": ""
   },
   "20": {
    "observador": ""
   },
   "23": {
    "observador": ""
   }
  },
  "5074": {
   "piche": "1.2",
   "tanque_c": "0.8",
   "evaporigrafo": "0.5",
   "subsuelo": {
    "5": {
     "f1": "25.2",
     "f2": "33.0",
     "f3": "28.0"
    },
    "10": {
     "f1": "",
     "f2": "",
     "f3": ""
    },
    "15": {
     "f1": "25.4",
     "f2": "34.2",
     "f3": "28.4"
    },
    "20": {
     "f1": "",
     "f2": "",
     "f3": ""
    },
    "25": {
     "f1": "",
     "f2": "",
     "f3": ""
    },
    "50": {
     "f1": "29.4",
     "f2": "29.0",
     "f3": "29.4"
    },
    "100": {
     "f1": "28.0",
     "f2": "28.0",
     "f3": "28.2"
    }
   },
   "notas": "Durante la madrugada cielo cubierto con llovizna; a partir de las 09:00 se abrió a nubes dispersas y se registró tormenta eléctrica local entre las 16:10 y 16:45 con ráfagas de viento del sureste.",
   "iniciales_obs": "KMC",
   "iniciales_grupos": {
    "2": "KMM",
    "8": "PR",
    "14": "PR",
    "20": "KMC"
   },
   "fenomenos": [
    {
     "hora": "00:15",
     "raf_dir": "",
     "raf_vel": "",
     "intensidad": "",
     "fenomeno": "RA",
     "inicio": "00:10",
     "final": "00:40",
     "duracion": "30",
     "iniciales": "KMM"
    },
    {
     "hora": "14:30",
     "raf_dir": "",
     "raf_vel": "",
     "intensidad": "F",
     "fenomeno": "DZ",
     "inicio": "14:20",
     "final": "15:05",
     "duracion": "45",
     "iniciales": "PR"
    },
    {
     "hora": "16:20",
     "raf_dir": "16",
     "raf_vel": "4.0",
     "intensidad": "F",
     "fenomeno": "TS",
     "inicio": "16:10",
     "final": "16:45",
     "duracion": "35",
     "iniciales": "PR"
    },
    {
     "hora": "19:00",
     "raf_dir": "",
     "raf_vel": "",
     "intensidad": "",
     "fenomeno": "V",
     "inicio": "18:50",
     "final": "19:10",
     "duracion": "20",
     "iniciales": "KMC"
    }
   ]
  }
 }
}
```

## Contexto de transformación (resumen del hilo de trabajo)

- El convertidor es **dos procesos independientes**: Proceso A lee las **hojas
  Z** (`0006Z…0003Z`) y arma `synop` + `datos`; Proceso B lee las **hojas CLI**
  (`3074`, `4074`, `5074`). Sin synop no se guarda CLI.
- Los Excel existentes son cuatro variantes de layout (V1/V2 páginas
  normales, V3 hoja ancha de Central, V4 desplazada una columna; el formato
  viejo no trae CLI). Detección por **cabecera real**, nunca por nombre de
  archivo ni por estación.
- Estación y fecha salen del **contenido** (fila 3 de una hoja del día: col 3
  estación, col 4 fecha ISO). Lectura desde 06Z/12Z, porque 00Z/03Z
  pertenecen al día anterior (cierre a las 06Z).
- Presión en formato viejo (4 celdas): `int(dígitos)/10` y si da menos de 1000
  se le suma 1000 (el decodificador del oráculo estaba mal para valores por
  debajo de 1000).
- Especificaciones y decisiones en `odd/tasks/transformacion-excel.md`.
