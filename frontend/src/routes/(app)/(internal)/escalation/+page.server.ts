import { BASE_API_URL } from '$lib/utils/constants';
import type { PageServerLoad, Actions } from './$types';

export const load: PageServerLoad = async ({ fetch, locals }) => {
	try {
		const ctrlRes = await fetch(`${BASE_API_URL}/control-assignments/controls/`);
		const rulesRes = await fetch(`${BASE_API_URL}/escalation-rules/`);
		const logsRes = await fetch(`${BASE_API_URL}/escalation/logs/`);
		const repoRes = await fetch(`${BASE_API_URL}/evidence-repository/`);
		const adminUsersRes = await fetch(`${BASE_API_URL}/escalation/admin-users/`);

		let controlsList: any[] = [];
		let frameworks: any[] = [];
		const usersMap = new Map<string, { id: string; email: string }>();

		if (ctrlRes.ok) {
			const ctrlData = await ctrlRes.json();
			frameworks = (ctrlData.frameworks || []).map((fw: any) => ({ id: fw.id, name: fw.name }));

			for (const fw of ctrlData.frameworks || []) {
				for (const c of fw.controls || []) {
					if (c.assignment && c.assignment.spoc_user && c.assignment.spoc_user.id) {
						controlsList.push({
							...c,
							framework_name: fw.name,
							framework_id: fw.id
						});

						if (c.assignment.spoc_user?.id) {
							usersMap.set(c.assignment.spoc_user.id, {
								id: c.assignment.spoc_user.id,
								email: c.assignment.spoc_user.email
							});
						}
						if (c.assignment.reviewer_user?.id) {
							usersMap.set(c.assignment.reviewer_user.id, {
								id: c.assignment.reviewer_user.id,
								email: c.assignment.reviewer_user.email
							});
						}
					}
				}
			}
		}

		let pendingLinks: any[] = [];
		if (repoRes.ok) {
			const repoData = await repoRes.json();
			pendingLinks = repoData.results || repoData || [];
		}

		let rules: any[] = [];
		if (rulesRes.ok) {
			const rData = await rulesRes.json();
			rules = rData.results || rData || [];
		}

		let logs: any[] = [];
		if (logsRes.ok) {
			const lData = await logsRes.json();
			logs = lData.results || lData || [];
		}

		let adminUsers: any[] = [];
		if (adminUsersRes.ok) {
			adminUsers = await adminUsersRes.json();
		}

		return {
			controls: controlsList,
			frameworks,
			assignedUsers: Array.from(usersMap.values()),
			adminUsers,
			pendingLinks,
			rules,
			logs,
			currentUser: locals.user || null
		};
	} catch (err) {
		console.error('Error loading escalation data:', err);
		return { controls: [], frameworks: [], assignedUsers: [], adminUsers: [], pendingLinks: [], rules: [], logs: [], currentUser: locals.user || null };
	}
};

export const actions: Actions = {
	saveRule: async ({ fetch, request }) => {
		const formData = await request.formData();
		const id = formData.get('id')?.toString();
		const name = formData.get('name')?.toString() || '';
		const is_active = formData.get('is_active') === 'true';
		const level = parseInt(formData.get('level')?.toString() || '1');
		const interval_value = parseInt(formData.get('interval_value')?.toString() || '1');
		const interval_unit = formData.get('interval_unit')?.toString() || 'minutes';
		const recipient_role = formData.get('recipient_role')?.toString() || 'SPOC';
		const target_admin_user_id = formData.get('target_admin_user_id')?.toString() || null;
		const trigger_baseline = formData.get('trigger_baseline')?.toString() || 'ASSIGNMENT_DATE';

		if (!id) {
			return { success: false, error: 'Missing rule ID.' };
		}

		try {
			const res = await fetch(`${BASE_API_URL}/escalation-rules/${id}/`, {
				method: 'PATCH',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					name,
					is_active,
					trigger_baseline,
					level,
					interval_value,
					interval_unit,
					recipient_role,
					target_admin_user_id
				})
			});

			if (res.ok) {
				const data = await res.json();
				return { success: true, data };
			} else {
				let errText = 'Failed to save rule.';
				try {
					const err = await res.json();
					errText = err.detail || err.error || JSON.stringify(err);
				} catch (e) {}
				return { success: false, error: errText };
			}
		} catch (err: any) {
			return { success: false, error: err.message || 'Server error saving rule.' };
		}
	},
	triggerEscalation: async ({ fetch, request }) => {
		const formData = await request.formData();
		const level = formData.get('level')?.toString() || '1';
		const assignment_ids_raw = formData.get('assignment_ids')?.toString() || '[]';
		const assignment_ids = JSON.parse(assignment_ids_raw);

		try {
			const res = await fetch(`${BASE_API_URL}/escalation/manual/`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ level: parseInt(level), assignment_ids })
			});

			if (res.ok) {
				const data = await res.json();
				return { success: true, data };
			} else {
				let errText = 'Failed to send escalation.';
				try {
					const err = await res.json();
					errText = err.error || errText;
				} catch (e) {}
				return { success: false, error: errText };
			}
		} catch (err: any) {
			return { success: false, error: err.message || 'Server error triggering escalation.' };
		}
	}
};
