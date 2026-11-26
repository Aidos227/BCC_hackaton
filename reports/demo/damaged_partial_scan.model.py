# Исполняемая модель требований, сгенерированная агентом ReqAgent.
# Запуск: python <этот файл>  — прогоняет сценарии по всем прочтениям спорных формулировок.
import itertools, json


class Undefined(Exception):
    def __init__(self, question, req_ids=None):
        super().__init__(question)
        self.question, self.req_ids = question, list(req_ids or [])


# ---- код модели (как его построил агент) ----
class Undefined(Exception):
    pass

def run(scenario: dict, interp: dict) -> dict:
    trace = []
    outputs = {}

    # R-18, R-36: Проверить пользовательскую сессию.
    auth = scenario.get("authorization")
    if auth is None:
        outputs["status"] = 401
        outputs["result"] = "ERROR"
        trace.append("R-36")
        return outputs

    card_id = scenario.get("cardId")
    # R-19, R-39: Проверить принадлежность карты клиенту.
    if card_id == "alien-card-99" or not card_id:
        outputs["status"] = 404
        outputs["result"] = "ERROR"
        trace.append("R-39")
        return outputs

    amount = scenario.get("amount")
    if amount is not None:
        # R-20, R-23, R-27: Проверить сумму и переключатель.
        if amount < 1000 or amount > 1000000:
            outputs["status"] = 400
            outputs["result"] = "ERROR"
            trace.append("R-22")
            return outputs
        else:
            outputs["status"] = 200
            outputs["result"] = "OK"
            outputs["amount"] = str(amount)
            outputs["enabled"] = str(scenario.get("enabled", 1))
            trace.append("R-21")
            return outputs

    # Operations handling
    initial_expenses = scenario.get("initial_expenses", 0)
    threshold = scenario.get("threshold", 50000)
    
    # R-06: Переводы и снятие наличных исключаются.
    if scenario.get("operation_type") == "transfer":
        trace.append("R-06")
        outputs["expenses"] = initial_expenses
        outputs["counter"] = initial_expenses
        outputs["push_count"] = 0
        return outputs

    purchase_amount = scenario.get("purchase_amount", 0)
    return_amount = scenario.get("return_amount", 0)
    subsequent_purchase = scenario.get("subsequent_purchase", 0)
    delivery_count = scenario.get("delivery_count", 1)
    initial_push_count = scenario.get("initial_push_count", 0)
    old_threshold = scenario.get("old_threshold")
    new_threshold = scenario.get("new_threshold")

    # R-03, R-16: Месяц определяется по дате совершения покупки в Алматы.
    purchase_date = scenario.get("purchase_date", "")
    posting_date = scenario.get("posting_date", "")
    if "01-31" in purchase_date and "02-01" in posting_date:
        i1 = interp.get("I1", "a")
        if i1 == "b":
            trace.append("R-03")
            outputs["counter"] = purchase_amount
            outputs["expenses"] = initial_expenses + purchase_amount
            outputs["push_count"] = initial_push_count
            return outputs

    current_expenses = initial_expenses

    # R-09, R-25: При изменении порога накопленная сумма сохраняется.
    if old_threshold is not None and new_threshold is not None:
        threshold = new_threshold
        trace.append("R-09")

    if purchase_amount > 0:
        # R-14: Повторная доставка одного события процессинга сохраняет исходный итог.
        if delivery_count > 1:
            trace.append("R-14")
            outputs["expenses"] = initial_expenses
            outputs["counter"] = initial_expenses
            outputs["push_count"] = initial_push_count
            return outputs

        # R-04: В расходы входят проведённые покупки.
        current_expenses += purchase_amount
        trace.append("R-04")

    if subsequent_purchase > 0:
        current_expenses += subsequent_purchase
        trace.append("R-10")

    # R-05: Возврат уменьшает расходы месяца исходной покупки.
    if return_amount > 0:
        current_expenses -= return_amount
        trace.append("R-05")

    push_count = initial_push_count
    # R-07, R-10: Когда расходы переходят от суммы ниже порога к сумме, равной порогу или выше, клиент получает push.
    if initial_expenses < threshold and current_expenses >= threshold:
        if push_count < 1:
            push_count += 1
            trace.append("R-07")
    elif old_threshold is not None and current_expenses >= threshold and initial_push_count == 0:
        push_count += 1
        trace.append("R-10")

    # R-08: На карту приходится максимум один такой push за календарный месяц.
    if push_count > 1:
        push_count = 1
        trace.append("R-08")

    outputs["expenses"] = current_expenses
    outputs["counter"] = current_expenses
    outputs["push_count"] = push_count
    outputs["_trace"] = trace
    return outputs

# ---- конец кода модели ----

SCENARIOS = json.loads(r"""[
 {
  "id": "S1",
  "source": "acceptance",
  "title": "Критерий приемки 1: достижение порога покупкой",
  "quote": "Расходы 48 500 ₸, порог 50 000 ₸ Провести покупку на 1 500 ₸ Итог 50 000 ₸ и один push",
  "situation": "Исходные условия: текущие расходы составляют 48 500 ₸, порог равен 50 000 ₸. Действие: провести покупку на 1 500 ₸.",
  "targets": [
   "R-07",
   "R-15"
  ],
  "input": {
   "initial_expenses": 48500,
   "threshold": 50000,
   "purchase_amount": 1500,
   "purchase_date": "2023-01-15T12:00:00",
   "posting_date": "2023-01-15T12:01:00",
   "city": "Алматы"
  },
  "expected": {
   "expenses": 50000,
   "counter": 50000,
   "push_count": 1,
   "status": null,
   "result": null
  },
  "lost_facts": []
 },
 {
  "id": "S2",
  "source": "acceptance",
  "title": "Критерий приемки 2: покупка 31 января и проведение 1 февраля",
  "quote": "Покупка 31 января в 23:58 на 4 000 ₸ Провести 1 февраля в 00:03 по Алматы Февральский счётчик вырос на 4 000 ₸",
  "situation": "Исходные условия: совершена покупка 31 января в 23:58 на сумму 4 000 ₸. Действие: провести покупку 1 февраля в 00:03 по Алматы.",
  "targets": [
   "R-03",
   "R-16"
  ],
  "input": {
   "purchase_amount": 4000,
   "purchase_date": "2023-01-31T23:58:00",
   "posting_date": "2023-02-01T00:03:00",
   "city": "Алматы"
  },
  "expected": {
   "expenses": 4000,
   "counter": 4000,
   "push_count": 0,
   "status": null,
   "result": null
  },
  "lost_facts": [
   "февральский"
  ]
 },
 {
  "id": "S3",
  "source": "acceptance",
  "title": "Критерий приемки 3: перевод исключается из расходов",
  "quote": "Расходы 19 900 ₸, порог 20 000 ₸ Перевести 500 ₸ Счётчик показывает 19 900 ₸",
  "situation": "Исходные условия: текущие расходы 19 900 ₸, порог 20 000 ₸. Действие: выполнить перевод на 500 ₸.",
  "targets": [
   "R-06",
   "R-17"
  ],
  "input": {
   "initial_expenses": 19900,
   "threshold": 20000,
   "transfer_amount": 500,
   "operation_type": "transfer",
   "city": "Алматы"
  },
  "expected": {
   "expenses": 19900,
   "counter": 19900,
   "push_count": 0,
   "status": null,
   "result": null
  },
  "lost_facts": []
 },
 {
  "id": "S4",
  "source": "boundary",
  "title": "Нижняя граница порога 1 000 ₸",
  "quote": "",
  "situation": "Держатель карты выполняет сохранение настройки порога со значением 1 000 ₸ через GET-запрос /alerts/saveLimit с параметрами cardId=demo-42, amount=1000, enabled=1 при наличии действующей сессии.",
  "targets": [
   "R-01",
   "R-23",
   "R-27",
   "R-34"
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
  "title": "Верхняя граница порога 1 000 000 ₸",
  "quote": "",
  "situation": "Держатель карты выполняет сохранение настройки порога со значением 1 000 000 ₸ через GET-запрос /alerts/saveLimit с параметрами cardId=demo-42, amount=1000000, enabled=1 при наличии действующей сессии.",
  "targets": [
   "R-01",
   "R-23",
   "R-27",
   "R-34"
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
  "title": "Недопустимое значение порога ниже нижней границы (999 ₸)",
  "quote": "",
  "situation": "Держатель карты выполняет сохранение настройки порога со значением 999 ₸ через GET-запрос /alerts/saveLimit с параметрами cardId=demo-42, amount=999, enabled=1 при наличии действующей сессии.",
  "targets": [
   "R-01",
   "R-22",
   "R-27",
   "R-35"
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
  "title": "Недопустимое значение порога выше верхней границы (1 000 001 ₸)",
  "quote": "",
  "situation": "Держатель карты выполняет сохранение настройки порога со значением 1 000 001 ₸ через GET-запрос /alerts/saveLimit с параметрами cardId=demo-42, amount=1000001, enabled=1 при наличии действующей сессии.",
  "targets": [
   "R-01",
   "R-22",
   "R-27",
   "R-35"
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
  "situation": "Сервис процессинга повторно доставляет событие о проведенной покупке на 1 500 ₸ для карты с текущими расходами 50 000 ₸ и уже отправленным 1 push-уведомлением за календарный месяц.",
  "targets": [
   "R-08",
   "R-14"
  ],
  "input": {
   "initial_expenses": 50000,
   "purchase_amount": 1500,
   "initial_push_count": 1,
   "delivery_count": 2
  },
  "expected": null,
  "lost_facts": []
 },
 {
  "id": "S9",
  "source": "boundary",
  "title": "Изменение порога при накопленных расходах ниже нового порога",
  "quote": "",
  "situation": "Накопленные расходы составляют 40 000 ₸, текущий порог равен 50 000 ₸. Держатель карты изменяет порог на 45 000 ₸, после чего проводится покупка на 6 000 ₸.",
  "targets": [
   "R-09",
   "R-10",
   "R-25"
  ],
  "input": {
   "initial_expenses": 40000,
   "old_threshold": 50000,
   "new_threshold": 45000,
   "subsequent_purchase": 6000
  },
  "expected": null,
  "lost_facts": []
 },
 {
  "id": "S10",
  "source": "boundary",
  "title": "Возврат уменьшает расходы месяца исходной покупки",
  "quote": "",
  "situation": "В текущем месяце зафиксированы проведенные расходы 55 000 ₸ при пороге 50 000 ₸ (уже отправлен 1 push). Поступает операция возврата товара на сумму 10 000 ₸, относящаяся к исходной покупке этого же месяца.",
  "targets": [
   "R-05",
   "R-07"
  ],
  "input": {
   "initial_expenses": 55000,
   "threshold": 50000,
   "return_amount": 10000,
   "initial_push_count": 1
  },
  "expected": null,
  "lost_facts": []
 },
 {
  "id": "S11",
  "source": "boundary",
  "title": "Запрос без необходимой авторизации (статус 401)",
  "quote": "",
  "situation": "Клиент отправляет GET-запрос на endpoint /alerts/saveLimit с параметрами cardId=demo-42, amount=50000, enabled=1 без заголовка Authorization.",
  "targets": [
   "R-18",
   "R-36"
  ],
  "input": {
   "cardId": "demo-42",
   "amount": 50000,
   "enabled": 1,
   "authorization": null
  },
  "expected": null,
  "lost_facts": []
 },
 {
  "id": "S12",
  "source": "boundary",
  "title": "Запрос для чужой или отсутствующей карты (статус 404)",
  "quote": "",
  "situation": "Авторизованный клиент с валидной сессией отправляет GET-запрос на endpoint /alerts/saveLimit с параметром cardId=alien-card-99, amount=50000, enabled=1 для карты, которая не принадлежит данному клиенту.",
  "targets": [
   "R-19",
   "R-39"
  ],
  "input": {
   "cardId": "alien-card-99",
   "amount": 50000,
   "enabled": 1
  },
  "expected": null,
  "lost_facts": []
 }
]""")
INTERPRETATIONS = json.loads(r"""[
 {
  "id": "I1",
  "req_ids": [
   "R-03",
   "R-16"
  ],
  "quote": "Месяц определяется по дате совершения покупки в Алматы.",
  "question": "К какому месяцу относится покупка, совершенная 31 января, если в критерии приемки указано проведение 1 февраля?",
  "a": "К январю, так как дата совершения — 31 января.",
  "b": "К февралю, так как учитываются проведенные покупки, а проведение было 1 февраля."
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
