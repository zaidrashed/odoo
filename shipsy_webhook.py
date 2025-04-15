from flask import Flask, request
import requests
import datetime

app = Flask(__name__)

# بيانات Odoo - غيّرها حسب حالتك
ODOO_URL = "http://localhost:8069/jsonrpc"
ODOO_DB = "odoo"
ODOO_UID = 2
ODOO_API_KEY = "b6bca92a44fc313ac091c36e5542fd00fdf1b0c6"

def convert_timestamp(ts):
    return datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d')

def call_odoo(model, method, args):
    payload = {
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
            "service": "object",
            "method": "execute_kw",
            "args": [ODOO_DB, ODOO_UID, ODOO_API_KEY, model, method, args]
        },
        "id": 1
    }
    response = requests.post(ODOO_URL, json=payload)
    result = response.json()
    if "error" in result:
        print("Odoo Error:", result["error"])
        return None
    return result.get("result")

@app.route("/shipsy-webhook", methods=["POST"])
def webhook():
    data = request.json
    print("Received data:", data)

    # قراءة البيانات من body
    invoice_number = data.get("invoice_number")
    customer_code = data.get("customer_code")
    invoice_amount = data.get("invoice_amount")
    invoice_date = convert_timestamp(data.get("invoice_created_at"))

    invoice_type = data.get("invoice_type")
    consignment_count = data.get("consignment_count")
    from_date = convert_timestamp(data.get("from_date"))
    to_date = convert_timestamp(data.get("to_date"))
    invoice_pdf_link = data.get("invoice_pdf_link")
    consignment_list_link = data.get("consignment_list_link")
    event = data.get("event")

    # 1. البحث عن العميل
    partner_ids = call_odoo("res.partner", "search", [[["ref", "=", customer_code]]])

    if partner_ids:
        partner_id = partner_ids[0]
    else:
        # 2. إنشاء العميل إذا غير موجود
        partner_id = call_odoo("res.partner", "create", [{
            "name": f"Customer {customer_code}",
            "ref": customer_code,
            "customer_rank": 1
        }])

    if not partner_id:
        return {"status": "error", "message": "Failed to find or create partner"}

    # 3. إنشاء الفاتورة مع معلومات إضافية
    invoice_id = call_odoo("account.move", "create", [{
        "move_type": "out_invoice",
        "invoice_date": invoice_date,
        "partner_id": partner_id,
        "ref": invoice_number,
        "narration": f"""
        Invoice Type: {invoice_type}
        Consignment Count: {consignment_count}
        Period: {from_date} to {to_date}
        Event: {event}
        PDF: {invoice_pdf_link}
        Consignment List: {consignment_list_link}
        """,
        "invoice_line_ids": [[0, 0, {
            "name": f"Shippsy Invoice {invoice_number}",
            "quantity": 1,
            "price_unit": invoice_amount
        }]]
    }])

    if not invoice_id:
        return {"status": "error", "message": "Failed to create invoice"}

    return {
        "status": "success",
        "invoice_id": invoice_id
    }

if __name__ == "__main__":
    app.run(port=5000)
