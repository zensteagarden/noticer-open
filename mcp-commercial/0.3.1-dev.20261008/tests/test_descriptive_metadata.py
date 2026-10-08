"""Public descriptive-metadata regression; no network or credentials."""
import asyncio,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import sales_mcp
from bootstrap import LazyAdapter
class DescriptionTests(unittest.TestCase):
 def setUp(self):
  self.server=sales_mcp.make_server(LazyAdapter())
  self.tools=asyncio.run(self.server.list_tools())
 def test_names_schemas_annotations_preserved(self):
  prior=json.loads((Path(__file__).parent/'metadata-baseline.json').read_text())
  current={t.name:{k:t.model_dump(mode='json')[k] for k in ('inputSchema','outputSchema','annotations')} for t in self.tools}
  self.assertEqual(current,prior)
 def test_instructions_have_trigger_and_bounds_before_client_truncation(self):
  value=self.server.instructions
  self.assertLess(len(value),2048)
  for term in ('before the next workflow action','public HTTPS JSON','known-good control','locally derived continue/block/hold','not signed permission','explicit owner consent','USD 1'):
   self.assertIn(term,value)
 def test_tools_describe_inputs_verification_and_payment_separation(self):
  descriptions={t.name:t.description for t in self.tools}
  for value in descriptions.values():self.assertLess(len(value),2048)
  for term in ('claim_ref','claim_id_path','deadline_seconds','authorized_public_read'):
   self.assertIn(term,descriptions['noticer_prepare_receipt'])
  self.assertIn('unsigned',descriptions['noticer_get_verified_receipt'])
  self.assertIn('can submit a real payment',descriptions['noticer_pay_with_existing_link'])
  self.assertIn('never a charge',descriptions['noticer_payment_challenge'])
