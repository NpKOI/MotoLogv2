import React from 'react';

const UploadPhotoButton: React.FC = () => {
    const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (file) {
            // Handle file upload logic here
        }
    };

    return (
        <label className="upload-photo-button">
            <input 
                type="file" 
                accept="image/*" 
                onChange={handleFileChange} 
                style={{ display: 'none' }} 
            />
            <span className="button-text">Upload Photo</span>
        </label>
    );
};

export default UploadPhotoButton;