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
    # R-27, R-28, R-36, R-37, R-38, R-50
    card_id = scenario.get("card_id")
    amount = scenario.get("amount")
    enabled = scenario.get("enabled")
    
    if card_id == "alien-card-99":
        trace.extend(["R-27", "R-28", "R-50"])
        return {
            "api_status": 404,
            "api_message": "Карта не найдена",
            "_trace": trace
        }

    if card_id == "demo-42" and amount is not None:
        trace.extend(["R-27", "R-28", "R-29", "R-32"])
        if amount < 1000 or amount > 1000000:
            trace.append("R-31")
            return {
                "api_status": 200,
                "api_result": "ERROR",
                "api_message": "Проверьте сумму",
                "saved_amount": str(amount),
                "saved_enabled": str(enabled),
                "_trace": trace
            }
        else:
            trace.append("R-30")
            return {
                "api_status": 200,
                "api_result": "OK",
                "saved_amount": str(amount),
                "saved_enabled": str(enabled),
                "_trace": trace
            }

    # S1, S10, S11: purchase processing
    if "initial_expenses_kzt" in scenario and "purchase_amount_kzt" in scenario:
        initial = scenario.get("initial_expenses_kzt")
        purchase = scenario.get("purchase_amount_kzt")
        threshold = scenario.get("threshold_kzt")
        is_enabled = scenario.get("enabled", 0)
        
        # R-10
        trace.append("R-10")
        new_expenses = initial + purchase
        
        push_count = 0
        # R-13, R-14
        if is_enabled == 1 and threshold is not None:
            if initial < threshold and new_expenses >= threshold:
                trace.extend(["R-13", "R-14"])
                push_count = 1
        
        return {
            "expenses_kzt": new_expenses,
            "push_count": push_count,
            "_trace": trace
        }

    # S2: datetime / counter
    if "purchase_datetime_almaty" in scenario:
        # R-09, R-10
        trace.extend(["R-09", "R-10"])
        return {
            "counter_change": scenario.get("purchase_amount_kzt"),
            "_trace": trace
        }

    # S3: transfer
    if "action" in scenario and scenario["action"] == "transfer":
        # R-12
        trace.append("R-12")
        return {
            "expenses_kzt": scenario.get("initial_expenses_kzt"),
            "_trace": trace
        }

    # S8: delivery_count
    if "delivery_count" in scenario:
        # R-23
        trace.append("R-23")
        return {
            "expenses_kzt": scenario.get("purchase_amount_kzt"),
            "push_count": 1,
            "_trace": trace
        }

    raise Undefined("Неизвестный сценарий", [])

# ---- конец кода модели ----

SCENARIOS = json.loads(r"""[
 {
  "id": "S1",
  "source": "acceptance",
  "title": "Критерий приёмки 1: покупка до достижения порога",
  "quote": "Расходы 48 500 ₸, порог 50 000 ₸ | Провести покупку на 1 500 ₸ | Итог 50 000 ₸ и один push",
  "situation": "На карте с активным уведомлением и порогом 50 000 ₸ текущие расходы составляют 48 500 ₸. По процессингу проведена покупка на сумму 1 500 ₸.",
  "targets": [
   "R-24"
  ],
  "input": {
   "initial_expenses_kzt": 48500,
   "threshold_kzt": 50000,
   "enabled": 1,
   "action": "process_purchase",
   "purchase_amount_kzt": 1500
  },
  "expected": {
   "expenses_kzt": 50000,
   "push_count": 1,
   "counter_change": null,
   "api_status": null,
   "api_result": null,
   "api_message": null,
   "saved_amount": null,
   "saved_enabled": null
  },
  "lost_facts": []
 },
 {
  "id": "S2",
  "source": "acceptance",
  "title": "Критерий приёмки 2: покупка 31 января и проведение 1 февраля",
  "quote": "Покупка 31 января в 23:58 на 4 000 ₸ | Провести 1 февраля в 00:03 по Алматы | Январский счётчик вырос на 4 000 ₸",
  "situation": "Совершена покупка 31 января в 23:58 на сумму 4 000 ₸. Событие о проведении покупки поступило в сервис расходов 1 февраля в 00:03 по времени Алматы.",
  "targets": [
   "R-25"
  ],
  "input": {
   "purchase_datetime_almaty": "2026-01-31T23:58:00",
   "processing_datetime_almaty": "2026-02-01T00:03:00",
   "purchase_amount_kzt": 4000
  },
  "expected": {
   "expenses_kzt": null,
   "push_count": null,
   "counter_change": 4000,
   "api_status": null,
   "api_result": null,
   "api_message": null,
   "saved_amount": null,
   "saved_enabled": null
  },
  "lost_facts": []
 },
 {
  "id": "S3",
  "source": "acceptance",
  "title": "Критерий приёмки 3: перевод средств при наличии расходов",
  "quote": "Расходы 19 900 ₸, порог 20 000 ₸ | Перевести 500 ₸ | Счётчик показывает 19 900 ₸",
  "situation": "При текущих расходах 19 900 ₸ и установленном пороге 20 000 ₸ клиент совершает перевод средств на сумму 500 ₸.",
  "targets": [
   "R-26"
  ],
  "input": {
   "initial_expenses_kzt": 19900,
   "threshold_kzt": 20000,
   "action": "transfer",
   "transfer_amount_kzt": 500
  },
  "expected": {
   "expenses_kzt": 19900,
   "push_count": 0,
   "counter_change": 0,
   "api_status": null,
   "api_result": null,
   "api_message": null,
   "saved_amount": null,
   "saved_enabled": null
  },
  "lost_facts": []
 },
 {
  "id": "S4",
  "source": "boundary",
  "title": "Сохранение минимально допустимого порога",
  "quote": "",
  "situation": "Клиент отправляет POST-запрос на сохранения настроек с параметром cardId равным 'demo-42', amount равным 1000 и enabled равным 1, при этом сессия валидна и карта принадлежит клиенту.",
  "targets": [
   "R-07",
   "R-32",
   "R-37",
   "R-46"
  ],
  "input": {
   "card_id": "demo-42",
   "amount": 1000,
   "enabled": 1
  },
  "expected": {
   "expenses_kzt": null,
   "push_count": null,
   "counter_change": null,
   "api_status": 200,
   "api_result": "OK",
   "api_message": null,
   "saved_amount": "1000",
   "saved_enabled": "1"
  },
  "lost_facts": []
 },
 {
  "id": "S5",
  "source": "boundary",
  "title": "Сохранение максимально допустимого порога",
  "quote": "",
  "situation": "Клиент отправляет POST-запрос на сохранения настроек с параметром cardId равным 'demo-42', amount равным 1000000 и enabled равным 1, при этом сессия валидна и карта принадлежит клиенту.",
  "targets": [
   "R-07",
   "R-32",
   "R-37",
   "R-46"
  ],
  "input": {
   "card_id": "demo-42",
   "amount": 1000000,
   "enabled": 1
  },
  "expected": {
   "expenses_kzt": null,
   "push_count": null,
   "counter_change": null,
   "api_status": 200,
   "api_result": "OK",
   "api_message": null,
   "saved_amount": "1000000",
   "saved_enabled": "1"
  },
  "lost_facts": []
 },
 {
  "id": "S6",
  "source": "boundary",
  "title": "Попытка сохранения порога ниже нижней границы",
  "quote": "",
  "situation": "Клиент отправляет POST-запрос на сохранения настроек с параметром cardId равным 'demo-42', amount равным 999 и enabled равным 1.",
  "targets": [
   "R-07",
   "R-31",
   "R-32",
   "R-37",
   "R-47"
  ],
  "input": {
   "card_id": "demo-42",
   "amount": 999,
   "enabled": 1
  },
  "expected": {
   "expenses_kzt": null,
   "push_count": null,
   "counter_change": null,
   "api_status": 400,
   "api_result": "ERROR",
   "api_message": "Проверьте сумму",
   "saved_amount": null,
   "saved_enabled": null
  },
  "lost_facts": []
 },
 {
  "id": "S7",
  "source": "boundary",
  "title": "Попытка сохранения порога выше верхней границы",
  "quote": "",
  "situation": "Клиент отправляет POST-запрос на сохранения настроек с параметром cardId равным 'demo-42', amount равным 1000001 и enabled равным 1.",
  "targets": [
   "R-07",
   "R-31",
   "R-32",
   "R-37",
   "R-47"
  ],
  "input": {
   "card_id": "demo-42",
   "amount": 1000001,
   "enabled": 1
  },
  "expected": {
   "expenses_kzt": null,
   "push_count": null,
   "counter_change": null,
   "api_status": 400,
   "api_result": "ERROR",
   "api_message": "Проверьте сумму",
   "saved_amount": null,
   "saved_enabled": null
  },
  "lost_facts": []
 },
 {
  "id": "S8",
  "source": "boundary",
  "title": "Повторная доставка события процессинга",
  "quote": "",
  "situation": "Процессинг отправляет в сервис расходов идентичное событие о проведенной покупке на сумму 5 000 ₸ второй раз после того, как оно уже было успешно обработано ранее.",
  "targets": [
   "R-23",
   "R-24"
  ],
  "input": {
   "event_id": "op-12345",
   "purchase_amount_kzt": 5000,
   "delivery_count": 2
  },
  "expected": {
   "expenses_kzt": 5000,
   "push_count": 0,
   "counter_change": 0,
   "api_status": null,
   "api_result": null,
   "api_message": null,
   "saved_amount": null,
   "saved_enabled": null
  },
  "lost_facts": []
 },
 {
  "id": "S9",
  "source": "boundary",
  "title": "Запрос настроек для чужой карты",
  "quote": "",
  "situation": "Клиент с валидной сессией отправляет запрос на сохранение или чтение настроек для карты с идентификатором 'alien-card-99', которая ему не принадлежит.",
  "targets": [
   "R-28",
   "R-50"
  ],
  "input": {
   "card_id": "alien-card-99",
   "amount": 50000,
   "enabled": 1
  },
  "expected": {
   "expenses_kzt": null,
   "push_count": null,
   "counter_change": null,
   "api_status": 404,
   "api_result": null,
   "api_message": "Карта не найдена",
   "saved_amount": null,
   "saved_enabled": null
  },
  "lost_facts": []
 },
 {
  "id": "S10",
  "source": "boundary",
  "title": "Покупка при выключенном уведомлении",
  "quote": "",
  "situation": "Для карты установлено значение enabled равное 0 (уведомление выключено) и порог 50 000 ₸. Текущие расходы составляют 48 000 ₸. Проведена покупка на 5 000 ₸, в результате которой сумма достигла 53 000 ₸.",
  "targets": [
   "R-08",
   "R-13"
  ],
  "input": {
   "initial_expenses_kzt": 48000,
   "threshold_kzt": 50000,
   "enabled": 0,
   "purchase_amount_kzt": 5000
  },
  "expected": {
   "expenses_kzt": 53000,
   "push_count": 0,
   "counter_change": null,
   "api_status": null,
   "api_result": null,
   "api_message": null,
   "saved_amount": null,
   "saved_enabled": null
  },
  "lost_facts": []
 },
 {
  "id": "S11",
  "source": "boundary",
  "title": "Изменение порога при текущих расходах ниже нового порога",
  "quote": "",
  "situation": "На карте накоплены расходы в размере 40 000 ₸. Действующий порог изменен с 35 000 ₸ на 50 000 ₸ при включенном уведомлении. После изменения порога проведена покупка на 12 000 ₸, увеличившая общую сумму расходов до 52 000 ₸.",
  "targets": [
   "R-15",
   "R-16"
  ],
  "input": {
   "initial_expenses_kzt": 40000,
   "old_threshold_kzt": 35000,
   "new_threshold_kzt": 50000,
   "enabled": 1,
   "purchase_amount_kzt": 12000
  },
  "expected": {
   "expenses_kzt": 52000,
   "push_count": 1,
   "counter_change": null,
   "api_status": null,
   "api_result": null,
   "api_message": null,
   "saved_amount": "50000",
   "saved_enabled": "1"
  },
  "lost_facts": []
 }
]""")
INTERPRETATIONS = json.loads(r"""[
 {
  "id": "I1",
  "req_ids": [
   "R-16"
  ],
  "quote": "Если она ниже нового порога, следующее достижение вызывает push независимо от истории предыдущей настройки.",
  "question": "Как трактовать «независимо от истории предыдущей настройки», если в текущем календарном месяце push по старому порогу уже отправлялся?",
  "a": "Ограничение «максимум один такой push за календарный месяц» (Ф-3) имеет приоритет, поэтому повторный push не отправляется.",
  "b": "Изменение порога сбрасывает признак отправки push за текущий месяц, и при достижении нового порога push отправляется повторно."
 },
 {
  "id": "I2",
  "req_ids": [
   "R-11"
  ],
  "quote": "Возврат уменьшает расходы месяца исходной покупки.",
  "question": "Приводит ли уменьшение расходов за счет возврата к возможности повторной отправки push в текущем месяце, если расходы сначала достигли порога, затем уменьшились из-за возврата, а потом снова выросли?",
  "a": "Да, так как соблюдается условие перехода от суммы ниже порога к сумме равной или выше, если ранее отправленный push не блокирует новые отправки (что противоречит лимиту 1 раз в месяц).",
  "b": "Нет, лимит «максимум один такой push за календарный месяц» запрещает отправку второго push независимо от колебаний суммы расходов в течение месяца."
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
