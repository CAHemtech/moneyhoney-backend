from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
import os
import json
import traceback

app = FastAPI(title="MoneyHoney Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

GOOGLE_SHEET_NAME = "SreehariTrackerBot"

USER_SHEETS = {
    "Hemachandra": "Hemachandra",
    "Sreehari":    "Sreehari",
    "Prashanth":   "Prashanth",
}

def get_sheet(user_name: str):
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    sa_json = os.environ.get("SERVICE_ACCOUNT_JSON")
    if not sa_json:
        raise Exception("SERVICE_ACCOUNT_JSON env variable not set!")
    
    sa_info = json.loads(sa_json)
    creds = Credentials.from_service_account_info(sa_info, scopes=scopes)
    client = gspread.authorize(creds)
    spreadsheet = client.open(GOOGLE_SHEET_NAME)

    tab_name = USER_SHEETS.get(user_name)
    if not tab_name:
        raise Exception(f"Unknown user: {user_name}")

    try:
        sheet = spreadsheet.worksheet(tab_name)
    except gspread.WorksheetNotFound:
        sheet = spreadsheet.add_worksheet(title=tab_name, rows=1000, cols=7)
        sheet.append_row(["Sl No", "Date", "Amount", "Transaction Type", "Remarks", "Timestamp"])

    return sheet

def get_next_sl_no(sheet):
    return len(sheet.get_all_values())

class Transaction(BaseModel):
    user: str
    date: str
    amount: float
    transaction_type: str
    remarks: str = ""

class UserRequest(BaseModel):
    user: str

@app.get("/")
def health():
    return {"status": "MoneyHoney backend running 🍯"}

@app.post("/save")
def save_transaction(txn: Transaction):
    try:
        sheet     = get_sheet(txn.user)
        sl_no     = get_next_sl_no(sheet)
        timestamp = datetime.now().strftime("%d-%b-%y %H:%M:%S")
        sheet.append_row([
            sl_no, txn.date, txn.amount,
            txn.transaction_type, txn.remarks, timestamp
        ])
        return {"success": True, "sl_no": sl_no}
    except Exception as e:
        print("SAVE ERROR:", traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/transactions")
def get_transactions(req: UserRequest):
    try:
        sheet   = get_sheet(req.user)
        records = sheet.get_all_values()
        if len(records) <= 1:
            return {"transactions": []}
        txns = []
        for row in records[1:]:
            if len(row) >= 4 and row[1]:
                txns.append({
                    "sl_no":    row[0] if len(row) > 0 else "",
                    "date":     row[1] if len(row) > 1 else "",
                    "amount":   float(row[2]) if len(row) > 2 and row[2] else 0,
                    "type":     row[3] if len(row) > 3 else "",
                    "remarks":  row[4] if len(row) > 4 else "",
                    "timestamp":row[5] if len(row) > 5 else "",
                })
        return {"transactions": txns}
    except Exception as e:
        print("TRANSACTIONS ERROR:", traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/balance")
def get_balance(req: UserRequest):
    try:
        result = get_transactions(req)
        txns   = result["transactions"]
        bal    = sum(t["amount"] if t["type"]=="Paid" else -t["amount"] for t in txns)
        return {
            "balance":     bal,
            "abs_balance": abs(bal),
            "direction":   "settled" if bal==0 else "owed_to_you" if bal>0 else "you_owe"
        }
    except Exception as e:
        print("BALANCE ERROR:", traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
