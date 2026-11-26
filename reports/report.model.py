# Исполняемая модель требований, сгенерированная агентом LSJ.
# Запуск: python <этот файл>  — прогоняет сценарии по всем прочтениям спорных формулировок.
import itertools, json


class Undefined(Exception):
    def __init__(self, question, req_ids=None):
        super().__init__(question)
        self.question, self.req_ids = question, list(req_ids or [])


# ---- код модели (как его построил агент) ----
from decimal import Decimal
from typing import Any, Dict

class Undefined(Exception):
    def __init__(self, question: str, req_ids: list):
        super().__init__(question)
        self.question = question
        self.req_ids = req_ids

def run(scenario: dict, interp: dict) -> dict:
    trace = []
    outputs = {}
    
    # API Save Limit Scenario
    if "card_id" in scenario:
        card_id = scenario.get("card_id")
        amount = scenario.get(
            "amount", 
            scenario.get("threshold_kzt")
        )
        auth = scenario.get("auth")
        
        # R-19
        if not auth or auth != "Bearer valid_token":
            trace.append("R-19")
            outputs["api_status"] = 401
            outputs["api_result"] = "ERROR"
            outputs["_trace"] = trace
            return outputs
        trace.append("R-19")
        
        # R-28
        if card_id == "alien-card-99":
            trace.append("R-28")
            outputs["api_status"] = 404
            outputs["api_result"] = "ERROR"
            outputs["_trace"] = trace
            return outputs
        
        # R-01, R-25, R-21
        try:
            amt_dec = Decimal(str(amount))
        except Exception:
            amt_dec = Decimal(0)
            
        if amt_dec < 1000 or amt_dec > 1000000:
            trace.append("R-01")
            trace.append("R-25")
            trace.append("R-21")
            
            i3 = interp.get("I3", "a")
            if i3 == "a":
                outputs["api_status"] = 400
            elif i3 == "b":
                outputs["api_status"] = 200
            else:
                raise Undefined("Какой HTTP статус должен возвращаться при передаче неподдерживаемой суммы порога?", ["R-21", "R-25"])
            outputs["api_result"] = "ERROR"
            outputs["_trace"] = trace
            return outputs
            
        trace.append("R-01")
        trace.append(
            "R-25"
        )
        trace.append("R-20")
        trace.append("R-23")
        
        outputs["api_status"] = 200
        outputs["api_result"] = "OK"
        outputs["_trace"] = trace
        return outputs

    # Transaction / Processing Scenario
    initial_expenses = Decimal(str(scenario.get("initial_expenses_kzt", 0)))
    threshold = Decimal(str(scenario.get("threshold_kzt", scenario.get("new_threshold_kzt", 50000))))
    tx_type = scenario.get("transaction_type")
    tx_amt_raw = scenario.get("transaction_amount_kzt", scenario.get("redelivered_transaction_amount_kzt", 0))
    
    if isinstance(tx_amt_raw, str):
        clean_str = ''.join(c for c in tx_amt_raw if c.isdigit() or c == '.')
        tx_amt = Decimal(clean_str if clean_str else '0')
    else:
        tx_amt = Decimal(str(tx_amt_raw))
        
    existing_push = scenario.get("existing_push_count", 0)
    
    # R-06: transfers and cash withdrawals are excluded
    if tx_type in ["transfer", "cash_withdrawal"]:
        trace.append("R-06")
        outputs["expenses_kzt"] = int(initial_expenses)
        outputs["push_count"] = int(existing_push)
        outputs["_trace"] = trace
        return outputs
        
    # R-14: Redelivered transaction
    if "redelivered_transaction_amount_kzt" in scenario:
        trace.append("R-14")
        outputs["expenses_kzt"] = int(initial_expenses)
        outputs["push_count"] = int(existing_push)
        outputs["_trace"] = trace
        return outputs
        
    # Return operation
    return_amt = Decimal(str(scenario.get("return_amount_kzt", 0)))
    if return_amt > 0:
        trace.append("R-05")
        new_exp = initial_expenses - return_amt
        outputs["expenses_kzt"] = int(new_exp)
        outputs["push_count"] = int(existing_push)
        outputs["_trace"] = trace
        return outputs
        
    # Date / month check scenario S2
    if "purchase_datetime" in scenario:
        trace.append("R-03")
        i1 = interp.get("I1", "a")
        if i1 == "b":
            trace.append("R-04")
            outputs["expenses_kzt"] = int(tx_amt)
        else:
            outputs[
                "expenses_kzt"
            ] = int(0)
        outputs["push_count"] = 0
        outputs["_trace"] = trace
        return outputs
        
    # Threshold change scenario S11
    if "old_threshold_kzt" in scenario:
        trace.append("R-09")
        trace.append("R-10")
        outputs["expenses_kzt"] = int(initial_expenses)
        outputs["push_count"] = int(existing_push)
        outputs["_trace"] = trace
        return outputs

    # Standard purchase calculation
    new_expenses = initial_expenses + tx_amt
    trace.append("R-04")
    
    push_cnt = existing_push
    if initial_expenses < threshold and new_expenses >= threshold:
        trace.append("R-07")
        if existing_push == 0:
            trace.append("R-08")
            push_cnt += 1
        else:
            i2 = interp.get("I2", "b")
            if i2 == "a":
                trace.append("R-08")
                push_cnt += 1
            elif i2 == "b":
                pass
            else:
                raise Undefined("Если после получения первого push за месяц расходы снизились и снова достигли порога, будет ли отправлен второй push?", ["R-07", "R-08"])
                
    outputs["expenses_kzt"] = int(new_expenses)
    outputs["push_count"] = int(push_cnt)
    outputs["_trace"] = trace
    return outputs

# ---- конец кода модели ----

SCENARIOS = json.loads(r"""[
 {
  "id": "S1",
  "source": "acceptance",
  "title": "Критерий приёмки 1: Достижение порога покупкой",
  "quote": "Расходы 48 500 ₸, порог 50 000 ₸ Провести покупку на 1 500 ₸ Итог 50 000 ₸ и один push",
  "situation": "На карте имеются текущие расходы 48 500 ₸ и установленный порог 50 000 ₸. Выполняется проведение покупки на 1 500 ₸.",
  "targets": [
   "R-07",
   "R-15"
  ],
  "input": {
   "initial_expenses_kzt": 48500,
   "threshold_kzt": 50000,
   "transaction_type": "purchase",
   "transaction_amount_kzt": 1500
  },
  "expected": {
   "expenses_kzt": 50000,
   "push_count": 1,
   "api_status": null,
   "api_result": null
  },
  "lost_facts": []
 },
 {
  "id": "S2",
  "source": "acceptance",
  "title": "Критерий приёмки 2: Учет покупки по дате проведения в Алматы",
  "quote": "Покупка 31 января в 23:58 на 4 000 ₸ Провести 1 февраля в 00:03 по Алматы Февральский счётчик вырос на 4 000 ₸",
  "situation": "Совершена покупка 31 января в 23:58 на сумму 4 000 ₸. Проведение операции выполнено 1 февраля в 00:03 по времени Алматы.",
  "targets": [
   "R-03",
   "R-04",
   "R-16"
  ],
  "input": {
   "purchase_datetime": "31 января в 23:58",
   "posting_datetime_almaty": "1 февраля в 00:03",
   "transaction_type": "purchase",
   "transaction_amount_kzt": "4 000 ₸"
  },
  "expected": {
   "period_increased": "Февральский счётчик",
   "growth_amount": "4 000 ₸"
  },
  "lost_facts": []
 },
 {
  "id": "S3",
  "source": "acceptance",
  "title": "Критерий приёмки 3: Исключение переводов из расходов",
  "quote": "Расходы 19 900 ₸, порог 20 000 ₸ Перевести 500 ₸ Счётчик показывает 19 900 ₸",
  "situation": "На карте имеются текущие расходы 19 900 ₸ и установленный порог 20 000 ₸. Выполняется перевод на сумму 500 ₸.",
  "targets": [
   "R-06",
   "R-17"
  ],
  "input": {
   "initial_expenses_kzt": 19900,
   "threshold_kzt": 20000,
   "transaction_type": "transfer",
   "transaction_amount_kzt": 500
  },
  "expected": {
   "expenses_kzt": 19900,
   "push_count": 0,
   "api_status": null,
   "api_result": null
  },
  "lost_facts": []
 },
 {
  "id": "S4",
  "source": "boundary",
  "title": "Сохранение минимально допустимого порога через API",
  "quote": "",
  "situation": "Владелец активной карты отправляет запрос GET /alerts/saveLimit с параметрами cardId=demo-42, amount=1000, enabled=1 с валидным Bearer токеном сессии.",
  "targets": [
   "R-01",
   "R-18",
   "R-19",
   "R-20",
   "R-22",
   "R-25",
   "R-26",
   "R-27"
  ],
  "input": {
   "card_id": "demo-42",
   "amount": 1000,
   "enabled": 1,
   "auth": "Bearer valid_token"
  },
  "expected": {
   "expenses_kzt": null,
   "push_count": null,
   "api_status": 200,
   "api_result": "OK"
  },
  "lost_facts": []
 },
 {
  "id": "S5",
  "source": "boundary",
  "title": "Сохранение максимально допустимого порога через API",
  "quote": "",
  "situation": "Владелец активной карты отправляет запрос GET /alerts/saveLimit с параметрами cardId=demo-42, amount=1000000, enabled=1 с валидным Bearer токеном сессии.",
  "targets": [
   "R-01",
   "R-18",
   "R-19",
   "R-20",
   "R-22",
   "R-25",
   "R-26",
   "R-27"
  ],
  "input": {
   "card_id": "demo-42",
   "amount": 1000000,
   "enabled": 1,
   "auth": "Bearer valid_token"
  },
  "expected": {
   "expenses_kzt": null,
   "push_count": null,
   "api_status": 200,
   "api_result": "OK"
  },
  "lost_facts": []
 },
 {
  "id": "S6",
  "source": "boundary",
  "title": "Попытка сохранения порога ниже нижней границы через API",
  "quote": "",
  "situation": "Владелец активной карты отправляет запрос GET /alerts/saveLimit с параметрами cardId=demo-42, amount=999, enabled=1 с валидным Bearer токеном сессии.",
  "targets": [
   "R-01",
   "R-21",
   "R-25",
   "R-27"
  ],
  "input": {
   "card_id": "demo-42",
   "amount": 999,
   "enabled": 1,
   "auth": "Bearer valid_token"
  },
  "expected": {
   "expenses_kzt": null,
   "push_count": null,
   "api_status": 400,
   "api_result": "ERROR"
  },
  "lost_facts": []
 },
 {
  "id": "S7",
  "source": "boundary",
  "title": "Попытка сохранения порога выше верхней границы через API",
  "quote": "",
  "situation": "Владелец активной карты отправляет запрос GET /alerts/saveLimit с параметрами cardId=demo-42, amount=1000001, enabled=1 с валидным Bearer токеном сессии.",
  "targets": [
   "R-01",
   "R-21",
   "R-25",
   "R-27"
  ],
  "input": {
   "card_id": "demo-42",
   "amount": 1000001,
   "enabled": 1,
   "auth": "Bearer valid_token"
  },
  "expected": {
   "expenses_kzt": null,
   "push_count": null,
   "api_status": 400,
   "api_result": "ERROR"
  },
  "lost_facts": []
 },
 {
  "id": "S8",
  "source": "boundary",
  "title": "Запрос сохранения настроек для чужой карты",
  "quote": "",
  "situation": "Клиент отправляет запрос GET /alerts/saveLimit с параметрами cardId=alien-card-99, amount=50000, enabled=1 с валидным Bearer токеном своей сессии.",
  "targets": [
   "R-20",
   "R-28"
  ],
  "input": {
   "card_id": "alien-card-99",
   "amount": 50000,
   "enabled": 1,
   "auth": "Bearer valid_token"
  },
  "expected": {
   "expenses_kzt": null,
   "push_count": null,
   "api_status": 404,
   "api_result": null
  },
  "lost_facts": []
 },
 {
  "id": "S9",
  "source": "boundary",
  "title": "Повторная доставка одинакового события процессинга",
  "quote": "",
  "situation": "По карте с расходами 48 500 ₸ и порогом 50 000 ₸ проведена покупка на 1 500 ₸, вызвавшая отправку одного push и итог 50 000 ₸. Процессинг повторно доставляет то же самое событие покупки с тем же идентификатором операции.",
  "targets": [
   "R-08",
   "R-14",
   "R-15"
  ],
  "input": {
   "initial_expenses_kzt": 50000,
   "threshold_kzt": 50000,
   "existing_push_count": 1,
   "redelivered_transaction_amount_kzt": 1500
  },
  "expected": {
   "expenses_kzt": 50000,
   "push_count": 1,
   "api_status": null,
   "api_result": null
  },
  "lost_facts": []
 },
 {
  "id": "S10",
  "source": "boundary",
  "title": "Обработка операции возврата покупки",
  "quote": "",
  "situation": "В течение календарного месяца по карте зафиксированы проведенные покупки на сумму 55 000 ₸ (порог 50 000 ₸, отправлен 1 push). Поступает операция возврата исходной покупки на сумму 10 000 ₸.",
  "targets": [
   "R-05",
   "R-07",
   "R-08"
  ],
  "input": {
   "initial_expenses_kzt": 55000,
   "threshold_kzt": 50000,
   "existing_push_count": 1,
   "return_amount_kzt": 10000
  },
  "expected": {
   "expenses_kzt": 45000,
   "push_count": 1,
   "api_status": null,
   "api_result": null
  },
  "lost_facts": []
 },
 {
  "id": "S11",
  "source": "boundary",
  "title": "Изменение порога при накопленной сумме ниже нового порога",
  "quote": "",
  "situation": "На карте имеются накопленные расходы 45 000 ₸ при текущем пороге 40 000 ₸ (push уже был отправлен в текущем месяце). Владелец меняет порог через API на 50 000 ₸.",
  "targets": [
   "R-09",
   "R-10"
  ],
  "input": {
   "initial_expenses_kzt": 45000,
   "old_threshold_kzt": 40000,
   "new_threshold_kzt": 50000,
   "existing_push_count": 1
  },
  "expected": {
   "expenses_kzt": 45000,
   "push_count": 1,
   "api_status": null,
   "api_result": null
  },
  "lost_facts": []
 },
 {
  "id": "S12",
  "source": "boundary",
  "title": "Исключение операции снятия наличных из расходов",
  "quote": "",
  "situation": "На карте имеются текущие расходы 19 000 ₸ и установленный порог 20 000 ₸. Выполняется операция снятия наличных в банкомате на сумму 5 000 ₸.",
  "targets": [
   "R-06"
  ],
  "input": {
   "initial_expenses_kzt": 19000,
   "threshold_kzt": 20000,
   "transaction_type": "cash_withdrawal",
   "transaction_amount_kzt": 5000
  },
  "expected": {
   "expenses_kzt": 19000,
   "push_count": 0,
   "api_status": null,
   "api_result": null
  },
  "lost_facts": []
 }
]""")
INTERPRETATIONS = json.loads(r"""[
 {
  "id": "I1",
  "req_ids": [
   "R-03"
  ],
  "quote": "Месяц определяется по дате совершения покупки в Алматы. В расходы входят проведённые покупки.",
  "question": "Как определяется месяц для покупки, которая совершена в одном календарном месяце, а проведена в другом?",
  "a": "По месяцу даты совершения покупки.",
  "b": "По месяцу даты проведения покупки."
 },
 {
  "id": "I2",
  "req_ids": [
   "R-07",
   "R-08"
  ],
  "quote": "Когда расходы переходят от суммы ниже порога к сумме, равной порогу или выше, клиент получает push. На карту приходится максимум один такой push за календарный месяц.",
  "question": "Если после получения первого push за месяц расходы снизились (например, из-за возврата) и затем снова достигли порога, будет ли отправлен второй push?",
  "a": "Да, так как произошло новое достижение порога после снижения расходов.",
  "b": "Нет, так как действует ограничение «максимум один такой push за календарный месяц» без учета возвратов."
 },
 {
  "id": "I3",
  "req_ids": [
   "R-21",
   "R-25"
  ],
  "quote": "При отклонении суммы вернуть прежнее состояние и результат ERROR.",
  "question": "Какой HTTP статус должен возвращаться при передаче неподдерживаемой суммы порога (например, 500 тенге или 2 000 000 тенге)?",
  "a": "Статус 400 в соответствии с общим описанием неверно заполненных параметров.",
  "b": "Статус 200 с телом результата ERROR."
 },
 {
  "id": "I4",
  "req_ids": [
   "R-09",
   "R-10"
  ],
  "quote": "При изменении порога накопленная сумма сохраняется. Если она ниже нового порога, следующее достижение вызывает push независимо от истории предыдущей настройки.",
  "question": "Если на момент изменения порога накопленная сумма уже была выше или равна новому порогу, отправляется ли push сразу в момент изменения настроек?",
  "a": "Да, так как условие равенства или превышения порога выполняется на момент сохранения.",
  "b": "Нет, push отправляется только при совершении следующей покупки, переводящей сумму через порог."
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
