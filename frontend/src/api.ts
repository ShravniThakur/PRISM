import axios from 'axios';

// Layer 1: Cryptographic Authentication
export const LAYER1_API = 'http://localhost:8000';
// Layer 2: Deepfake/Phishing AI Models
export const LAYER2_API = 'http://localhost:8001';
// Layer 3: Central Brain & Threat Reports
export const LAYER3_API = 'http://localhost:8002';

export const api = {
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
    
    analyzeMedia: async (file: File) => {
        const formData = new FormData();
        formData.append("file", file);
        try {
            const res = await axios.post(`${LAYER2_API}/analyze/media`, formData);
            return res.data;
        } catch (e) {
             console.error("Layer 2 Media API Failed", e);
             return { video_fake_score: 0, audio_fake_score: 0, segmented_video_scores: [], segmented_audio_scores: [] };
        }
    },
    
    analyzeText: async (text: string) => {
        try {
            const res = await axios.post(`${LAYER2_API}/analyze/text`, { text });
            return res.data;
        } catch (e) {
            console.error("Layer 2 Text API Failed", e);
            return { final_text_score: 0, segmented_text_scores: [] };
        }
    },
    
    getFinalScore: async (payload: {
        text_score: number;
        video_score: number;
        audio_score: number;
        domain: string | null;
        is_authenticated_sender: number;
        raw_text: string | null;
        segmented_text_scores: number[];
        segmented_video_scores: number[];
        segmented_audio_scores: number[];
    }) => {
        try {
            const res = await axios.post(`${LAYER3_API}/brain/score`, payload);
            return res.data;
        } catch (e) {
            console.error("Layer 3 Score API Failed", e);
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

    prepareSignature: async (file: File) => {
        const formData = new FormData();
        formData.append("file", file);
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
