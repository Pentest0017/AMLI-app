import { BASE_API_URL } from '$lib/utils/constants';
import { contentDispositionHeader } from '$lib/utils/contentDisposition';
import { error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async ({ fetch, request, cookies, setHeaders, params }) => {
	const token = cookies.get('token');
	const cookieHeader = request.headers.get('cookie') || '';
	const endpoint = `${BASE_API_URL}/evidences/${params.id}/attachment/`;

	const reqHeaders: Record<string, string> = {
		cookie: cookieHeader
	};
	if (token) {
		reqHeaders['Authorization'] = `Token ${token}`;
	}

	try {
		const attachmentResponse = await fetch(endpoint, {
			headers: reqHeaders
		});

		// Handle specific HTTP error statuses gracefully
		if (attachmentResponse.status === 401) {
			return error(401, 'Authentication required to access this evidence attachment.');
		}
		if (attachmentResponse.status === 404) {
			return error(404, 'No file attachment available for this evidence item.');
		}
		if (attachmentResponse.status === 403) {
			return error(403, 'Access denied to this evidence attachment.');
		}
		if (!attachmentResponse.ok) {
			return error(attachmentResponse.status as any, `Unable to fetch evidence attachment (HTTP ${attachmentResponse.status}).`);
		}

		const contentType =
			attachmentResponse.headers.get('Content-Type') || 'application/octet-stream';
		const contentDisposition = attachmentResponse.headers.get('Content-Disposition');

		if (!contentDisposition) {
			throw new Error('Missing Content-Disposition header');
		}

		const fileName = contentDisposition.split('filename=')[1]?.replace(/"/g, '').trim();
		if (!fileName) {
			throw new Error('Invalid filename in Content-Disposition');
		}

		if (!attachmentResponse.body) {
			throw new Error('No response body');
		}

		const reader = attachmentResponse.body.getReader();

		const stream = new ReadableStream({
			start(controller) {
				function push() {
					reader
						.read()
						.then(({ done, value }) => {
							if (done) {
								controller.close();
								return;
							}
							controller.enqueue(value);
							push();
						})
						.catch((err) => {
							console.error('Stream reading error:', err);
							controller.error(err);
						});
				}
				push();
			},
			cancel() {
				reader.cancel().catch(() => {});
			}
		});

		setHeaders({
			'Content-Type': contentType,
			'Content-Disposition': contentDispositionHeader(fileName)
		});

		return new Response(stream, {
			status: attachmentResponse.status
		});
	} catch (err: any) {
		if (err && typeof err === 'object' && 'status' in err) {
			throw err;
		}
		console.error('Attachment fetch error:', err);
		return error(500, 'Failed to fetch attachment');
	}
};
