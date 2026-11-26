# Исполняемая модель требований, сгенерированная агентом ReqAgent.
# Запуск: python <этот файл>  — прогоняет сценарии по всем прочтениям спорных формулировок.
import itertools, json


class Undefined(Exception):
    def __init__(self, question, req_ids=None):
        super().__init__(question)
        self.question, self.req_ids = question, list(req_ids or [])


# ---- код модели (как его построил агент) ----
from decimal import Decimal
from datetime import datetime

class Undefined(Exception):
    def __init__(self, message, req_ids):
        super().__init__(message)
        self.req_ids = req_ids

def run(scenario: dict, interp: dict) -> dict:
    trace = []
    outputs = {}

    if "expenses_initial" in scenario and "purchase_amount" in scenario:
        trace.append("R-08")
        init = Decimal(str(scenario["expenses_initial"]))
        purch = Decimal(str(scenario["purchase_amount"]))
        limit = Decimal(str(scenario.get("limit_kzt", 50000)))
        total = init + purch
        outputs["expenses_total"] = float(total)
        outputs["limit_kzt"] = float(limit)
        if init < limit and total >= limit:
            trace.append("R-11")
            outputs["push_count"] = 1
        else:
            outputs["push_count"] = 0
            
    elif "purchase_time_almaty" in scenario:
        trace.append("R-07")
        p_time = datetime.fromisoformat(scenario["purchase_time_almaty"])
        outputs["counter_month"] = f"{p_time.year}-{p_time.month:02d}"
        if "posting_time_almaty" in scenario:
            trace.append("R-08")
            purch = Decimal(str(scenario.get("purchase_amount", 0)))
            outputs["expenses_total"] = float(purch)

    elif "transfer_amount" in scenario:
        trace.append("R-10")
        init = Decimal(str(scenario["expenses_initial"]))
        outputs["expenses_total"] = float(init)
        outputs["limit_kzt"] = float(scenario["limit_kzt"])

    elif "amount" in scenario and "cardId" in scenario:
        trace.append("R-05")
        trace.append("R-31")
        amt = int(scenario["amount"])
        en = int(scenario["enabled"])
        if 1000 <= amt <= 1000000:
            outputs["api_result"] = {"status": 200, "body": {"result": "OK", "amount": str(amt), "enabled": str(en)}}
            outputs["limit_kzt"] = amt
            outputs["enabled"] = en
        else:
            outputs["api_result"] = {"status": 200, "body": {"result": "ERROR", "message": "Проверьте сумму"}}

    elif "initial_expenses" in scenario and "duplicate_operation_amount" in scenario:
        trace.append("R-21")
        outputs["expenses_total"] = float(scenario["initial_expenses"])

    elif "current_month_expenses" in scenario and "return_amount" in scenario:
        trace.append("R-09")
        cur = Decimal(str(scenario["current_month_expenses"]))
        ret = Decimal(str(scenario["return_amount"]))
        outputs["expenses_total"] = float(cur - ret)

    elif "existing_push_count" in scenario:
        trace.append("R-12")
        outputs["push_count"] = int(scenario["existing_push_count"])
        outputs["expenses_total"] = float(scenario["expenses_current"])
        outputs["limit_kzt"] = float(scenario["limit_kzt"])

    outputs["_trace"] = trace
    return outputs

# ---- конец кода модели ----

SCENARIOS = json.loads(r"""[
 {
  "id": "S1",
  "source": "acceptance",
  "title": "Достижение порога расходов с отправкой push",
  "quote": "Расходы 48 500 ₸, порог 50 000 ₸ Провести покупку на 1 500 ₸ Итог 50 000 ₸ и один push",
  "situation": "Исходные условия: расходы 48 500 ₸, порог 50 000 ₸. Действие: провести покупку на 1 500 ₸.",
  "targets": [
   "R-22"
  ],
  "input": {
   "expenses_initial": 48500,
   "limit_kzt": 50000,
   "purchase_amount": 1500
  },
  "expected": {
   "expenses_total": 50000,
   "push_count": 1
  },
  "lost_facts": []
 },
 {
  "id": "S2",
  "source": "acceptance",
  "title": "Учет покупки по времени Алматы на стыке месяцев",
  "quote": "Покупка 31 января в 23:58 на 4 000 ₸ Провести 1 февраля в 00:03 по Алматы Февральский счётчик вырос на 4 000 ₸",
  "situation": "Исходные условия: покупка совершена 31 января в 23:58 на 4 000 ₸. Действие: провести 1 февраля в 00:03 по Алматы.",
  "targets": [
   "R-23",
   "R-07"
  ],
  "input": {
   "purchase_time_almaty": "2023-01-31T23:58:00",
   "posting_time_almaty": "2023-02-01T00:03:00",
   "purchase_amount": 4000
  },
  "expected": {
   "counter_month": "February",
   "expenses_total": 4000
  },
  "lost_facts": []
 },
 {
  "id": "S3",
  "source": "acceptance",
  "title": "Исключение переводов из счетчика расходов",
  "quote": "Расходы 19 900 ₸, порог 20 000 ₸ Перевести 500 ₸ Счётчик показывает 19 900 ₸",
  "situation": "Исходные условия: расходы 19 900 ₸, порог 20 000 ₸. Действие: перевести 500 ₸.",
  "targets": [
   "R-24",
   "R-10"
  ],
  "input": {
   "expenses_initial": 19900,
   "limit_kzt": 20000,
   "transfer_amount": 500
  },
  "expected": {
   "expenses_total": 19900
  },
  "lost_facts": []
 },
 {
  "id": "S4",
  "source": "boundary",
  "title": "Попытка установить порог ниже минимального значения",
  "quote": "• Ф-1. Держатель активной карты KZT задаёт целый порог от 1 000 до 1 000 000 ₸ включительно.",
  "situation": "Клиент передает в запросе сохранения порог со значением 999 ₸.",
  "targets": [
   "R-05",
   "R-31",
   "R-36"
  ],
  "input": {
   "cardId": "demo-42",
   "amount": 999,
   "enabled": 1
  },
  "expected": {
   "api_result": "400"
  },
  "lost_facts": []
 },
 {
  "id": "S5",
  "source": "boundary",
  "title": "Установка порога на нижней граничном значении",
  "quote": "• Ф-1. Держатель активной карты KZT задаёт целый порог от 1 000 до 1 000 000 ₸ включительно.",
  "situation": "Клиент передает в запросе сохранения порог со значением 1 000 ₸.",
  "targets": [
   "R-05",
   "R-31",
   "R-36"
  ],
  "input": {
   "cardId": "demo-42",
   "amount": 1000,
   "enabled": 1
  },
  "expected": {
   "api_result": "200"
  },
  "lost_facts": []
 },
 {
  "id": "S6",
  "source": "boundary",
  "title": "Установка порога на верхней граничном значении",
  "quote": "• Ф-1. Держатель активной карты KZT задаёт целый порог от 1 000 до 1 000 000 ₸ включительно.",
  "situation": "Клиент передает в запросе сохранения порог со значением 1 000 000 ₸.",
  "targets": [
   "R-05",
   "R-31",
   "R-36"
  ],
  "input": {
   "cardId": "demo-42",
   "amount": 1000000,
   "enabled": 1
  },
  "expected": {
   "api_result": "200"
  },
  "lost_facts": []
 },
 {
  "id": "S7",
  "source": "boundary",
  "title": "Попытка установить порог выше максимального значения",
  "quote": "• Ф-1. Держатель активной карты KZT задаёт целый порог от 1 000 до 1 000 000 ₸ включительно.",
  "situation": "Клиент передает в запросе сохранения порог со значением 1 000 001 ₸.",
  "targets": [
   "R-05",
   "R-31",
   "R-36"
  ],
  "input": {
   "cardId": "demo-42",
   "amount": 1000001,
   "enabled": 1
  },
  "expected": {
   "api_result": "400"
  },
  "lost_facts": []
 },
 {
  "id": "S8",
  "source": "boundary",
  "title": "Повторная доставка одного события процессинга",
  "quote": "Повторная доставка одного события процессинга сохраняет исходный итог.",
  "situation": "Покупка на 1 000 ₸ уже была доставлена и учтена в расходах. Процессинг повторно отправляет точно такое же событие.",
  "targets": [
   "R-21"
  ],
  "input": {
   "initial_expenses": 5000,
   "duplicate_operation_amount": 1000
  },
  "expected": {
   "expenses_total": 5000
  },
  "lost_facts": []
 },
 {
  "id": "S9",
  "source": "boundary",
  "title": "Возврат покупки уменьшает расходы месяца исходной покупки",
  "quote": "Возврат уменьшает расходы месяца исходной покупки.",
  "situation": "В текущем месяце расходы составляют 15 000 ₸. Поступает операция возврата на 5 000 ₸ по покупке, совершенной в прошлом месяце.",
  "targets": [
   "R-09"
  ],
  "input": {
   "current_month_expenses": 15000,
   "return_amount": 5000,
   "original_purchase_month": "previous"
  },
  "expected": {
   "expenses_total": 15000,
   "counter_month": "previous_affected"
  },
  "lost_facts": []
 },
 {
  "id": "S10",
  "source": "boundary",
  "title": "Отправка максимум одного push за календарный месяц при повторном достижении порога",
  "quote": "На карту приходится максимум один такой push за календарный месяц.",
  "situation": "Расходы достигли порога, клиент уже получил 1 push в текущем календарном месяце. После этого расходы уменьшились (возвратом) и снова достигли порога.",
  "targets": [
   "R-12"
  ],
  "input": {
   "existing_push_count": 1,
   "expenses_current": 50000,
   "limit_kzt": 50000
  },
  "expected": {
   "push_count": 1
  },
  "lost_facts": []
 }
]""")
INTERPRETATIONS = json.loads(r"""[
 {
  "id": "I1",
  "req_ids": [
   "R-26"
  ],
  "quote": "REST type GET",
  "question": "Метод сохранения настроек описан с типом GET, однако логика предполагает изменение состояния (сохранение порога и переключателя). Корректен ли выбор HTTP-метода GET для операции сохранения?",
  "a": "Метод должен оставаться GET в соответствии с буквальным текстом документа",
  "b": "Метод должен быть изменен на POST/PUT в соответствии с REST-стандартами для операций изменения данных"
 }
]""")

if __name__ == "__main__":
    ids = [i["id"] for i in INTERPRETATIONS][:4]
    combos = [dict(zip(ids, v)) for v in itertools.product("ab", repeat=len(ids))] or [{}]
    for s in SCENARIOS:
        print(f"\n{s['id']} [{s.get('source')}] {s.get('title')}")
        if s.get("expected"):
            print("  ожидается по документу:", s["expected"])
        for c in combos:
            try:
                r = run(s.get("input") or {}, dict(c))
                print(" ", c or "", "→", r)
            except Undefined as u:
                print(" ", c or "", "→ НЕ ОПРЕДЕЛЕНО:", u.question)
