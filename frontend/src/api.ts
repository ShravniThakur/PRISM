import axios from 'axios';

// Layer 1: Cryptographic Authentication
export const LAYER1_API = 'http://localhost:8000';
// Layer 2: Deepfake/Phishing AI Models
export const LAYER2_API = 'http://localhost:8001';
// Layer 3: Central Brain & Threat Reports
export const LAYER3_API = 'http://localhost:8002';

// Add interceptor to include JWT token if present
axios.interceptors.request.use((config) => {
    const token = localStorage.getItem('prism_token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

export const api = {
    googleLogin: async (token: string) => {
        try {
            const res = await axios.post(`${LAYER3_API}/brain/auth/google`, { token });
            return res.data;
        } catch (e) {
            console.error("Login failed", e);
            throw e;
        }
    },

    verifySignature: async (input: { text?: string; file?: File }) => {
        const formData = new FormData();
        if (input.text) formData.append("text", input.text);
        if (input.file) formData.append("file", input.file);
        try {
            const res = await axios.post(`${LAYER1_API}/verify`, formData);
            return res.data;
        } catch (e) {
            console.error("Layer 1 API Failed", e);
            return { is_authenticated_sender: 0 };
        }
    },
    
    analyzeUnified: async (input: { text?: string; file?: File }) => {
        const formData = new FormData();
        if (input.text) formData.append("text", input.text);
        if (input.file) formData.append("file", input.file);
        try {
            const res = await axios.post(`${LAYER3_API}/brain/orchestrate`, formData);
            return res.data;
        } catch (e) {
            console.error("Unified Analysis API Failed", e);
            throw e;
        }
    },
    
    getScanHistory: async () => {
        try {
            const res = await axios.get(`${LAYER3_API}/brain/history`);
            return res.data;
        } catch (e) {
            console.error("Layer 3 History API Failed", e);
            return [];
        }
    },

    // Layer 1 Entity Portal APIs
    registerEntity: async (payload: { name: string; type: string }) => {
        try {
            const res = await axios.post(`${LAYER1_API}/entities`, payload);
            return res.data;
        } catch (e) {
            console.error("Failed to register entity", e);
            throw e;
        }
    },

    prepareSignature: async (input: { file?: File, text?: string }) => {
        const formData = new FormData();
        if (input.file) formData.append("file", input.file);
        if (input.text) formData.append("text", input.text);
        try {
            const res = await axios.post(`${LAYER1_API}/sign/prepare`, formData);
            return res.data;
        } catch (e) {
            console.error("Failed to prepare signature", e);
            throw e;
        }
    },

    submitSignature: async (payload: {
        entity_id: string;
        payload_b64: string;
        signature_b64: string;
        title?: string;
        reference_url?: string;
    }) => {
        try {
            const res = await axios.post(`${LAYER1_API}/sign/submit`, payload);
            return res.data;
        } catch (e) {
            console.error("Failed to submit signature", e);
            throw e;
        }
    },

    getEntityByName: async (name: string) => {
        try {
            const res = await axios.get(`${LAYER1_API}/entities/by-name/${encodeURIComponent(name)}`);
            return res.data;
        } catch (e) {
            console.error("Failed to get entity by name", e);
            throw e;
        }
    },

    rotateKey: async (entityId: string) => {
        try {
            const res = await axios.post(`${LAYER1_API}/entities/${entityId}/keys/rotate`);
            return res.data;
        } catch (e) {
            console.error("Failed to rotate key", e);
            throw e;
        }
    },

    getSignedAssets: async (entityId: string) => {
        try {
            const res = await axios.get(`${LAYER1_API}/entities/${entityId}/assets`);
            return res.data;
        } catch (e) {
            console.error("Failed to fetch signed assets", e);
            throw e;
        }
    }
};
