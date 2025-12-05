import React from 'react';

interface UserAvatarProps {
    imageUrl: string;
    altText?: string;
}

const UserAvatar: React.FC<UserAvatarProps> = ({ imageUrl, altText = 'User Avatar' }) => {
    return (
        <img 
            src={imageUrl} 
            alt={altText} 
            className="user-avatar" 
        />
    );
};

export default UserAvatar;