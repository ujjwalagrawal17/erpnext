import frappe
from erpnext.crm.doctype.utils import get_document_with_phone_number
import requests

# api/method/erpnext.erpnext_integrations.exotel_integration.handle_incoming_call

@frappe.whitelist(allow_guest=True)
def handle_incoming_call(*args, **kwargs):
	exotel_settings = get_exotel_settings()
	if not exotel_settings.enabled: return

	employee_email = kwargs.get('AgentEmail')
	status = kwargs.get('Status')

	if status == 'free':
		# call disconnected for agent
		# "and get_call_status(kwargs.get('CallSid')) in ['in-progress']" - additional check to ensure if the call was redirected
		frappe.publish_realtime('call_disconnected', user=employee_email)
		return

	call_log = get_call_log(kwargs)

	data = frappe._dict({
		'call_from': kwargs.get('CallFrom'),
		'agent_email': kwargs.get('AgentEmail'),
		'call_type': kwargs.get('Direction'),
		'call_log': call_log,
		'call_status_method': 'erpnext.erpnext_integrations.exotel_integration.get_call_status'
	})
	if call_log.call_status in ['ringing', 'in-progress']:
		frappe.publish_realtime('show_call_popup', data, user=data.agent_email)


def get_call_log(call_payload):
	communication = frappe.get_all('Communication', {
		'communication_medium': 'Phone',
		'call_id': call_payload.get('CallSid'),
	}, limit=1)

	if communication:
		communication = frappe.get_doc('Communication', communication[0].name)
	else:
		communication = frappe.new_doc('Communication')
		communication.subject = frappe._('Call from {}').format(call_payload.get("CallFrom"))
		communication.communication_medium = 'Phone'
		communication.phone_no = call_payload.get("CallFrom")
		communication.comment_type = 'Info'
		communication.communication_type = 'Communication'
		communication.sent_or_received = 'Received'
		communication.communication_date = call_payload.get('StartTime')
		communication.call_id = call_payload.get('CallSid')

	status = get_call_status(communication.call_id)
	communication.call_status = status or 'failed'
	communication.status = 'Closed' if status in ['completed', 'failed', 'no-answer'] else 'Open'
	communication.call_duration = call_payload.get('Duration') if status in ['completed', 'failed', 'no-answer'] else 0
	communication.content = 'call_payload'
	communication.save(ignore_permissions=True)
	frappe.db.commit()
	return communication

@frappe.whitelist()
def get_call_status(call_id):
	print(call_id)
	settings = get_exotel_settings()
	response = requests.get('https://{api_key}:{api_token}@api.exotel.com/v1/Accounts/erpnext/Calls/{call_id}.json'.format(
		api_key=settings.api_key,
		api_token=settings.api_token,
		call_id=call_id
	))
	status = response.json().get('Call', {}).get('Status')
	return status

@frappe.whitelist()
def make_a_call(from_number, to_number, caller_id):
	settings = get_exotel_settings()
	response = requests.post('https://{api_key}:{api_token}@api.exotel.com/v1/Accounts/{sid}/Calls/connect.json?details=true'.format(
		api_key=settings.api_key,
		api_token=settings.api_token,
	), data={
		'From': from_number,
		'To': to_number,
		'CallerId': caller_id
	})

	return response.json()

def get_exotel_settings():
	return frappe.get_single('Exotel Settings')