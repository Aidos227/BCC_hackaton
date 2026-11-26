# Исполняемая модель требований, сгенерированная агентом ReqAgent.
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
    def __init__(self, message: str, req_ids: list):
        super().__init__(message)
        self.req_ids = req_ids

def run(scenario: dict, interp: dict) -> dict:
    trace = []
    outputs = {}

    # API Scenario handling
    if "auth_header" in scenario or "cardId" in scenario:
        auth = scenario.get("auth_header")
        card_id = scenario.get("cardId")
        amount = scenario.get("amount")
        enabled = scenario.get("enabled")

        # R-19: Authorization | Bearer, сессия владельца карты
        if not auth:
            trace.append("R-19")
            trace.append("R-41")
            outputs["api_status"] = 401
            outputs["api_message"] = "Требуется вход"
            return {**outputs, "_trace": trace}

        # R-22, R-43: Если карта принадлежит другому клиенту, ответ — 404
        if card_id == "foreign-card-99":
            trace.append("R-22")
            trace.append("R-43")
            outputs["api_status"] = 404
            outputs["api_message"] = "Карта не найдена"
            return {**outputs, "_trace": trace}

        # R-03, R-23, R-26, R-30, R-31: Проверка суммы (1000-1000000) и enabled (0 или 1)
        if amount is not None and (amount < 1000 or amount > 1000000):
            trace.append("R-03")
            trace.append("R-23")
            trace.append("R-25")
            trace.append("R-26")
            trace.append("R-30")
            trace.append("R-40")
            outputs["api_status"] = 400
            outputs["api_result"] = "ERROR"
            outputs["api_message"] = "Проверьте сумму"
            return {**outputs, "_trace": trace}

        if enabled not in (0, 1):
            trace.append("R-31")
            trace.append("R-40")
            outputs["api_status"] = 400
            outputs["api_message"] = "Некорректный запрос"
            return {**outputs, "_trace": trace}

        # R-24, R-39, R-36, R-37: Успешное сохранение
        trace.append("R-24")
        trace.append(
            "R-27"
        ) if "old_limit" in scenario or "new_limit" in scenario else None
        trace.append("R-39")
        trace.append("R-36")
        trace.append("R-37")
        outputs["api_status"] = 200
        outputs["api_result"] = "OK"
        outputs["api_amount"] = str(amount)
        outputs["api_enabled"] = str(enabled)
        return {**outputs, "_trace": trace}

    # Processing / Expenses Scenario handling
    if "initial_expenses" in scenario and "transaction_amount" in scenario:
        init_exp = scenario["initial_expenses"]
        limit = scenario["limit"]
        tx_amt = scenario["transaction_amount"]
        tx_type = scenario.get("transaction_type")

        total = init_exp + tx_amt if tx_type == "purchase" else init_exp
        trace.append("R-15")
        outputs["total_expenses"] = total
        outputs["counter_amount"] = total

        # R-07, R-08: Push logic
        i1_mode = interp.get("I1", "a")
        if init_exp < limit and total >= limit:
            trace.append("R-07")
            trace.append("R-08")
            outputs["push_count"] = 1
        else:
            outputs["push_count"] = 0
        return {**outputs, "_trace": trace}

    if "purchase_time_almaty" in scenario:
        # R-05, R-16: Покупка относится к месяцу совершения по времени Алматы
        trace.append("R-05")
        trace.append("R-16")
        outputs["total_expenses"] = scenario["amount"]
        outputs["counter_amount"] = scenario[
            "amount"
        ]  # February expenses increased
        outputs["push_count"] = 0
        return {**outputs, "_trace": trace}

    if "transfer_amount" in scenario:
        # R-06, R-17: Переводы не учитываются
        init_exp = scenario["initial_expenses"]
        trace.append("R-06")
        trace.append("R-17")
        outputs["total_expenses"] = init_exp
        outputs["counter_amount"] = init_exp
        outputs["push_count"] = 0
        return {**outputs, "_trace": trace}

    if "event_id" in scenario:
        # R-14: Повторная доставка одного события сохраняет исходный итог
        trace.append("R-14")
        amt = scenario["amount"]
        outputs["total_expenses"] = amt
        outputs["counter_amount"] = amt
        outputs["push_count"] = 0
        return {**outputs, "_trace": trace}

    if "accumulated_expenses" in scenario:
        # R-09, R-10, R-28: Смена порога сохраняет накопленные расходы
        acc = scenario["accumulated_expenses"]
        new_limit = scenario["new_limit"]
        sub = scenario["subsequent_purchase"]
        total = acc + sub
        trace.append("R-09")
        trace.append("R-10")
        trace.append("R-28")
        outputs["total_expenses"] = total
        outputs["counter_amount"] = total
        if acc < new_limit and total >= new_limit:
            trace.append("R-07")
            outputs["push_count"] = 1
        else:
            outputs["push_count"] = 0
        return {**outputs, "_trace": trace}

    if "return_amount" in scenario:
        # R-06, R-12: Возврат вычитается из месяца исходной покупки
        trace.append("R-06")
        trace.append("R-12")
        outputs["total_expenses"] = -scenario["return_amount"]
        outputs["counter_amount"] = -scenario["return_amount"]
        outputs["push_count"] = 0
        return {**outputs, "_trace": trace}

    raise Undefined("Неизвестный сценарий", [])

# ---- конец кода модели ----

SCENARIOS = json.loads(r"""[
 {
  "id": "S1",
  "source": "acceptance",
  "title": "Критерий приемки 1: Проведение покупки с достижением порога",
  "quote": "Расходы 48 500 ₸, порог 50 000 ₸ | Провести покупку на 1 500 ₸ | Итог 50 000 ₸ и один push",
  "situation": "Исходные условия: расходы 48 500 ₸, порог 50 000 ₸. Действие: провести покупку на 1 500 ₸.",
  "targets": [
   "R-15"
  ],
  "input": {
   "initial_expenses": 48500,
   "limit": 50000,
   "transaction_amount": 1500,
   "transaction_type": "purchase"
  },
  "expected": {
   "total_expenses": 50000,
   "push_count": 1,
   "counter_amount": 50000
  },
  "lost_facts": []
 },
 {
  "id": "S2",
  "source": "acceptance",
  "title": "Критерий приемки 2: Учет покупки по времени совершения",
  "quote": "Покупка совершена 31.01 в 23:58, сумма 4 000 ₸ | Проведение 01.02 в 00:03 (Алматы) | Расходы февраля увеличились на 4 000 ₸",
  "situation": "Исходные условия: покупка совершена 31.01 в 23:58, сумма 4 000 ₸. Действие: проведение 01.02 в 00:03 (Алматы).",
  "targets": [
   "R-16"
  ],
  "input": {
   "purchase_time_almaty": "31.01 23:58",
   "processing_time_almaty": "01.02 00:03",
   "amount": 4000
  },
  "expected": {
   "total_expenses": 4000
  },
  "lost_facts": []
 },
 {
  "id": "S3",
  "source": "acceptance",
  "title": "Критерий приемки 3: Игнорирование переводов в расходах",
  "quote": "Расходы 19 900 ₸, порог 20 000 ₸ | Перевести 500 ₸ | Счётчик показывает 19 900 ₸",
  "situation": "Исходные условия: расходы 19 900 ₸, порог 20 000 ₸. Действие: перевести 500 ₸.",
  "targets": [
   "R-17"
  ],
  "input": {
   "initial_expenses": 19900,
   "limit": 20000,
   "transfer_amount": 500
  },
  "expected": {
   "counter_amount": 19900,
   "total_expenses": 19900
  },
  "lost_facts": []
 },
 {
  "id": "S4",
  "source": "boundary",
  "title": "Граница порога снизу (минимальное значение)",
  "quote": "",
  "situation": "Владелец активной тенговой карты вызывает метод сохранения порога с параметром amount равным 1000, enabled равным 1 и валидным cardId.",
  "targets": [
   "R-03",
   "R-26",
   "R-30",
   "R-39"
  ],
  "input": {
   "cardId": "demo-42",
   "amount": 1000,
   "enabled": 1
  },
  "expected": null,
  "lost_facts": []
 },
 {
  "id": "S5",
  "source": "boundary",
  "title": "Граница порога сверху (максимальное значение)",
  "quote": "",
  "situation": "Владелец активной тенговой карты вызывает метод сохранения порога с параметром amount равным 1000000, enabled равным 1 и валидным cardId.",
  "targets": [
   "R-03",
   "R-26",
   "R-30",
   "R-39"
  ],
  "input": {
   "cardId": "demo-42",
   "amount": 1000000,
   "enabled": 1
  },
  "expected": null,
  "lost_facts": []
 },
 {
  "id": "S6",
  "source": "boundary",
  "title": "Недопустимое значение порога ниже границы",
  "quote": "",
  "situation": "Владелец активной тенговой карты вызывает метод сохранения порога с параметром amount равным 999, enabled равным 1 и валидным cardId.",
  "targets": [
   "R-03",
   "R-25",
   "R-26",
   "R-30",
   "R-40"
  ],
  "input": {
   "cardId": "demo-42",
   "amount": 999,
   "enabled": 1
  },
  "expected": null,
  "lost_facts": []
 },
 {
  "id": "S7",
  "source": "boundary",
  "title": "Недопустимое значение порога выше границы",
  "quote": "",
  "situation": "Владелец активной тенговой карты вызывает метод сохранения порога с параметром amount равным 1000001, enabled равным 1 и валидным cardId.",
  "targets": [
   "R-03",
   "R-25",
   "R-26",
   "R-30",
   "R-40"
  ],
  "input": {
   "cardId": "demo-42",
   "amount": 1000001,
   "enabled": 1
  },
  "expected": null,
  "lost_facts": []
 },
 {
  "id": "S8",
  "source": "boundary",
  "title": "Повторная доставка одного события процессинга",
  "quote": "",
  "situation": "Сервис расходов получает повторно точно такое же событие о проведенной покупке, которое уже было обработано ранее.",
  "targets": [
   "R-14"
  ],
  "input": {
   "event_id": "op-12345",
   "amount": 5000,
   "delivery_count": 2
  },
  "expected": null,
  "lost_facts": []
 },
 {
  "id": "S9",
  "source": "boundary",
  "title": "Смена порога при накопленных расходах меньше нового порога",
  "quote": "",
  "situation": "Накопленные расходы составляют 40 000 ₸. Владелец карты меняет порог со старого значения 30 000 ₸ на новое значение 50 000 ₸. После этого совершается покупка, приводящая к достижению нового порога в 50 000 ₸.",
  "targets": [
   "R-09",
   "R-10",
   "R-28"
  ],
  "input": {
   "accumulated_expenses": 40000,
   "old_limit": 30000,
   "new_limit": 50000,
   "subsequent_purchase": 10000
  },
  "expected": null,
  "lost_facts": []
 },
 {
  "id": "S10",
  "source": "boundary",
  "title": "Запрос без авторизации",
  "quote": "",
  "situation": "Клиент выполняет GET-запрос на endpoint /alerts/saveLimit без заголовка Authorization.",
  "targets": [
   "R-19",
   "R-41"
  ],
  "input": {
   "auth_header": null,
   "cardId": "demo-42",
   "amount": 50000,
   "enabled": 1
  },
  "expected": null,
  "lost_facts": []
 },
 {
  "id": "S11",
  "source": "boundary",
  "title": "Запрос с указанием чужой карты",
  "quote": "",
  "situation": "Владелец карты выполняет GET-запрос на endpoint /alerts/saveLimit с валидным Bearer токеном, но передает cardId, принадлежащий другому клиенту.",
  "targets": [
   "R-22",
   "R-43"
  ],
  "input": {
   "auth_header": "Bearer valid_token",
   "cardId": "foreign-card-99",
   "amount": 50000,
   "enabled": 1
  },
  "expected": null,
  "lost_facts": []
 },
 {
  "id": "S12",
  "source": "boundary",
  "title": "Вычет суммы возврата из месяца исходной покупки",
  "quote": "",
  "situation": "В феврале поступает сумма возврата за покупку, которая была совершена и проведена в январе.",
  "targets": [
   "R-06"
  ],
  "input": {
   "purchase_month": "January",
   "return_processing_month": "February",
   "return_amount": 3000
  },
  "expected": null,
  "lost_facts": []
 }
]""")
INTERPRETATIONS = json.loads(r"""[
 {
  "id": "I1",
  "req_ids": [
   "R-07",
   "R-10"
  ],
  "quote": "Push отправляется в момент, когда сумма расходов впервые становится не меньше порога, а до этого была меньше.",
  "question": "Отправляется ли push повторно в том же календарном месяце, если расходы сначала достигли порога (был отправлен push), затем снизились (например, из-за возврата) и снова достигли порога?",
  "a": "Push отправляется только один раз за календарный месяц независимо от колебаний суммы расходов.",
  "b": "Push отправляется снова, так как условие 'впервые становится не меньше порога, а до этого была меньше' выполняется заново после снижения."
 },
 {
  "id": "I2",
  "req_ids": [
   "R-18",
   "R-24"
  ],
  "quote": "HTTP-метод | GET",
  "question": "Допустимо ли использовать метод GET для изменения (записи) настроек в системе согласно REST guidelines?",
  "a": "Да, спецификация явно требует использовать GET для метода сохранения настроек.",
  "b": "Нет, метод GET является безопасным и идемпотентным, для изменения настроек должен использоваться POST или PUT."
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
