import { BASE_API_URL } from '$lib/utils/constants';
import type { RequestHandler } from './$types';

export const POST: RequestHandler = async (event) => {
	let body = {};
	try {
		body = await event.request.json();
	} catch (e) {}

	const endpoint = `${BASE_API_URL}/compliance-assessments/${event.params.id}/generate-pdf-report/`;

	const res = await event.fetch(endpoint, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
			'Accept': 'application/pdf, application/json'
		},
		body: JSON.stringify(body)
	});

	if (!res.ok) {
		let errText = 'Failed to generate audit report PDF.';
		try {
			const errData = await res.json();
			errText = errData.error || errText;
		} catch (e) {}
		return new Response(JSON.stringify({ error: errText }), {
			status: res.status,
			headers: { 'Content-Type': 'application/json' }
		});
	}

	const pdfBuffer = await res.arrayBuffer();
	const disposition = res.headers.get('Content-Disposition') || 'attachment; filename="Audit_Report.pdf"';

	return new Response(pdfBuffer, {
		status: 200,
		headers: {
			'Content-Type': 'application/pdf',
			'Content-Disposition': disposition
		}
	});
};
