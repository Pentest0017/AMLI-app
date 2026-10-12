import { csrfToken } from '$lib/utils/csrf';

export async function getFeatureToggles() {
    const res = await fetch('/api/feature-toggles/', {
        headers: {
            'Accept': 'application/json'
        }
    });
    if (!res.ok) throw new Error('Failed to fetch toggles');
    return res.json();
}

export async function createFeatureToggle(data: any) {
    const res = await fetch('/api/feature-toggles/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-CSRFToken': csrfToken
        },
        body: JSON.stringify(data)
    });
    if (!res.ok) throw new Error('Failed to create toggle');
    return res.json();
}

export async function updateFeatureToggle(id: number | string, data: any) {
    const res = await fetch(`/api/feature-toggles/${id}/`, {
        method: 'PATCH',
        headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-CSRFToken': csrfToken
        },
        body: JSON.stringify(data)
    });
    if (!res.ok) throw new Error('Failed to update toggle');
    return res.json();
}
