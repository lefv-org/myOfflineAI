import { WEBUI_API_BASE_URL } from '$lib/constants';

export type WatchedDirectory = {
	id: string;
	path: string;
	name: string;
	knowledge_id: string | null;
	extensions: string | null;
	exclude_patterns: string | null;
	enabled: boolean;
	last_scan_at: number | null;
	created_at: number;
	updated_at: number;
};

export type WatchedDirectoryForm = {
	path: string;
	name: string;
	extensions?: string | null;
	exclude_patterns?: string | null;
};

export const getWatchedDirectories = async (token: string): Promise<WatchedDirectory[]> => {
	let error: any = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/filesystem/`, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const createWatchedDirectory = async (
	token: string,
	form: WatchedDirectoryForm
): Promise<WatchedDirectory> => {
	let error: any = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/filesystem/`, {
		method: 'POST',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		},
		body: JSON.stringify(form)
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const updateWatchedDirectory = async (
	token: string,
	id: string,
	form: WatchedDirectoryForm
): Promise<WatchedDirectory> => {
	let error: any = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/filesystem/${id}`, {
		method: 'PUT',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		},
		body: JSON.stringify(form)
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const deleteWatchedDirectory = async (token: string, id: string) => {
	let error: any = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/filesystem/${id}`, {
		method: 'DELETE',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const resyncWatchedDirectory = async (token: string, id: string) => {
	let error: any = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/filesystem/${id}/resync`, {
		method: 'POST',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};
