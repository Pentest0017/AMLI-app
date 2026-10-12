import { BASE_API_URL } from '$lib/utils/constants';
import type { PageServerLoad, Actions } from './$types';

export const load: PageServerLoad = async ({ fetch }) => {
	try {
		const [treeRes, repoRes] = await Promise.all([
			fetch(`${BASE_API_URL}/intermediary-compliance/repository/tree/`),
			fetch(`${BASE_API_URL}/evidence-repository/`)
		]);

		let treeData = null;
		if (treeRes.ok) {
			treeData = await treeRes.json();
		}

		let items: any[] = [];
		let frameworksTree: any[] = [];
		if (repoRes.ok) {
			const repoData = await repoRes.json();
			items = repoData.results || [];
			frameworksTree = repoData.frameworks_tree || [];
		}

		return { treeData, items, frameworksTree };
	} catch (err) {
		console.error('Failed to load evidence repository server data:', err);
		return { treeData: null, items: [], frameworksTree: [] };
	}
};

export const actions: Actions = {
	createFolder: async ({ fetch, request }) => {
		const formData = await request.formData();
		const name = formData.get('name')?.toString().trim();
		const folder_type = formData.get('folder_type')?.toString();
		const parent = formData.get('parent')?.toString();

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
	}
};
