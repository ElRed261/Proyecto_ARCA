import requests
import json

BASE_URL = "http://127.0.0.1:8000/api"
# Usamos el token de admin que ya tenemos o logueamos de nuevo
# Para simplificar, asumimos que el backend no requiere auth en estos endpoints por ahora 
# (Revisando router.py, no veo Depends(get_current_user), solo get_db. 
#  Si requiere auth, fallará y lo arreglaré).

def test_accounting_flow():
    # 1. Crear Cuentas
    print("1. Creando Cuentas...")
    caja = requests.post(f"{BASE_URL}/accounting/accounts", json={
        "code": "1.1.01",
        "name": "Caja General",
        "account_type": "ASSET",
        "is_imputable": True
    })
    print("Caja:", caja.status_code, caja.json())
    caja_id = caja.json().get("id")

    capital = requests.post(f"{BASE_URL}/accounting/accounts", json={
        "code": "3.1.01",
        "name": "Capital Social",
        "account_type": "EQUITY",
        "is_imputable": True
    })
    print("Capital:", capital.status_code, capital.json())
    capital_id = capital.json().get("id")

    # 2. Crear Asiento (Borrador)
    print("\n2. Creando Asiento Borrador...")
    entry_data = {
        "date": "2025-01-15",
        "description": "Aporte inicial de capital",
        "items": [
            {"account_id": caja_id, "debit": 1000.00, "credit": 0},
            {"account_id": capital_id, "debit": 0, "credit": 1000.00}
        ]
    }
    entry = requests.post(f"{BASE_URL}/accounting/entries", json=entry_data)
    print("Asiento:", entry.status_code, entry.json())
    entry_id = entry.json().get("id")

    # 3. Postear Asiento
    print(f"\n3. Posteando Asiento ID {entry_id}...")
    posted = requests.post(f"{BASE_URL}/accounting/entries/{entry_id}/post")
    print("Posteado:", posted.status_code, posted.json())

if __name__ == "__main__":
    test_accounting_flow()
