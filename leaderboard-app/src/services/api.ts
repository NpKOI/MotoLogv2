import axios from 'axios';

const API_BASE_URL = 'https://api.example.com'; // Replace with your actual API base URL

export const fetchLeaderboard = async () => {
    try {
        const response = await axios.get(`${API_BASE_URL}/leaderboard`);
        return response.data;
    } catch (error) {
        console.error('Error fetching leaderboard:', error);
        throw error;
    }
};

export const uploadProfilePicture = async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await axios.post(`${API_BASE_URL}/upload`, formData, {
            headers: {
                'Content-Type': 'multipart/form-data',
            },
        });
        return response.data;
    } catch (error) {
        console.error('Error uploading profile picture:', error);
        throw error;
    }
};