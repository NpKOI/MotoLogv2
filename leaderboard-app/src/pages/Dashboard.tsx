import React from 'react';
import Leaderboard from '../components/Leaderboard';
import UploadPhotoButton from '../components/UploadPhotoButton';

const Dashboard: React.FC = () => {
    return (
        <div className="dashboard">
            <h1>Leaderboard</h1>
            <Leaderboard />
            <UploadPhotoButton />
        </div>
    );
};

export default Dashboard;