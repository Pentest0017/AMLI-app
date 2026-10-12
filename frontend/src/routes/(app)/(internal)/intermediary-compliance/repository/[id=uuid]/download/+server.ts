import { BASE_API_URL } from '$lib/utils/constants';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async (event) => {
	const endpoint = `${BASE_API_URL}/intermediary-compliance/partner-reports/${event.params.id}/download/`;

	const res = await event.fetch(endpoint);

	if (!res.ok) {
		let errText = 'File attachment not found';
		try {
			const errData = await res.json();
			errText = errData.error || errText;
		} catch (e) {}
		return new Response(JSON.stringify({ error: errText }), {
			status: res.status,
			headers: { 'Content-Type': 'application/json' }
		});
	}

	const fileBuffer = await res.arrayBuffer();
	const contentType = res.headers.get('Content-Type') || 'application/octet-stream';
	const disposition = res.headers.get('Content-Disposition') || 'attachment; filename="report_attachment"';

	return new Response(fileBuffer, {
		status: 200,
		headers: {
			'Content-Type': contentType,
			'Content-Disposition': disposition
		}
	});
};
