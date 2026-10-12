import { BASE_API_URL } from '$lib/utils/constants';
import type { PageServerLoad, Actions } from './$types';

export const load: PageServerLoad = async ({ fetch, locals }) => {
	try {
		const res = await fetch(`${BASE_API_URL}/intermediary-compliance/repository/tree/`);
		if (res.ok) {
			const treeData = await res.json();
			return { treeData, currentUser: locals.user || null };
		}
	} catch (err) {
		console.error('Failed to load intermediary compliance repository tree:', err);
	}
	return { treeData: null, currentUser: locals.user || null };
};

export const actions: Actions = {
	createFolder: async ({ fetch, request }) => {
		const formData = await request.formData();
		const name = formData.get('name')?.toString().trim();
		const folder_type = formData.get('folder_type')?.toString();
		let parent = formData.get('parent')?.toString();

		if (!parent || parent === 'GL') {
			const treeRes = await fetch(`${BASE_API_URL}/intermediary-compliance/repository/tree/`);
			if (treeRes.ok) {
				const treeData = await treeRes.json();
				parent = treeData?.id;
			}
		}

		if (!name || !parent) {
			return { success: false, error: 'Folder name and parent are required.' };
		}

		const res = await fetch(`${BASE_API_URL}/intermediary-compliance/repository/`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ name, folder_type, parent })
		});

		if (res.ok) {
			const data = await res.json();
			return { success: true, data };
		} else {
			const err = await res.json();
			return { success: false, error: err.error || 'Failed to create folder.' };
		}
	},

	createReport: async ({ fetch, request }) => {
		const formData = await request.formData();
		const title = formData.get('title')?.toString().trim();
		const partner_folder_id = formData.get('partner_folder_id')?.toString();

		if (!title || !partner_folder_id) {
			return { success: false, error: 'Report title and partner folder are required.' };
		}

		const res = await fetch(`${BASE_API_URL}/intermediary-compliance/partner-reports/`, {
			method: 'POST',
			body: formData
		});

		if (res.ok) {
			const data = await res.json();
			return { success: true, data };
		} else {
			let errText = 'Failed to create report.';
			try {
				const err = await res.json();
				errText = err.error || errText;
			} catch (e) {}
			return { success: false, error: errText };
		}
	},

	copyPaste: async ({ fetch, request }) => {
		const formData = await request.formData();
		const id = formData.get('id')?.toString();
		const type = formData.get('type')?.toString(); // 'FOLDER' or 'FILE'
		const target_id = formData.get('target_id')?.toString();
		const mode = formData.get('mode')?.toString() || 'COPY';

		if (!id || !target_id) return { success: false, error: 'Missing parameters.' };

		const endpoint = type === 'FILE'
			? `${BASE_API_URL}/intermediary-compliance/partner-reports/${id}/copy-paste/`
			: `${BASE_API_URL}/intermediary-compliance/repository/${id}/copy-paste/`;

		const body = type === 'FILE'
			? { target_partner_id: target_id, mode }
			: { target_parent_id: target_id, mode };

		const res = await fetch(endpoint, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify(body)
		});

		if (res.ok) {
			return { success: true };
		} else {
			const err = await res.json();
			return { success: false, error: err.error || 'Copy/Paste failed.' };
		}
	},

	deleteItem: async ({ fetch, request }) => {
		const formData = await request.formData();
		const id = formData.get('id')?.toString();
		const type = formData.get('type')?.toString();

		if (!id) return { success: false, error: 'Missing item ID.' };

		const endpoint = type === 'FILE'
			? `${BASE_API_URL}/intermediary-compliance/partner-reports/${id}/`
			: `${BASE_API_URL}/intermediary-compliance/repository/${id}/`;

		const res = await fetch(endpoint, { method: 'DELETE' });
		if (res.ok) {
			return { success: true };
		} else {
			return { success: false, error: 'Delete failed.' };
		}
	}
};
