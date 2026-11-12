"""Case identity regression: offline decision-to-example correspondence only."""
import unittest
from entry_engine import RULE_IDS
from run_engine import run_document

def case(case_id):
    return {"case_id":case_id,"rule_id":RULE_IDS[0],"side":"BUY","at":100,
            "facts":{"sentiment_permission":{"value":"TWO_SIDED","known_at":101,"source":"synthetic-test"}}}

def document(cases):
    return {"mode":"ANNOTATED_OFFLINE","plan_id":"case-id-regression",
            "allowed_rules":[RULE_IDS[0]],"synthetic_only":True,"cases":cases}

class CaseIdentityTests(unittest.TestCase):
    def test_decisions_preserve_identity_and_order(self):
        result=run_document(document([case("lesson21-example1"),case("lesson22-example2")]))
        self.assertEqual([(x["case_id"],x["case_index"]) for x in result["decisions"]],
                         [("lesson21-example1",0),("lesson22-example2",1)])
        self.assertEqual([x["status"] for x in result["decisions"]],["REVIEW","REVIEW"])
        self.assertEqual(result["orders_sent"],0)

    def test_duplicate_identity_rejected(self):
        with self.assertRaisesRegex(ValueError,"Duplicate case_id"):
            run_document(document([case("same"),case("same")]))

    def test_blank_identity_rejected(self):
        with self.assertRaisesRegex(ValueError,"nonempty case_id"):
            run_document(document([case(" ")]))

    def test_legacy_missing_identity_deterministic(self):
        a=case("unused")
        del a["case_id"]
        self.assertEqual(run_document(document([a]))["decisions"][0]["case_id"],"case-0000")

if __name__=="__main__":
    unittest.main()
