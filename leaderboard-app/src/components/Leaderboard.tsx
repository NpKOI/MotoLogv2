import React from 'react';
import UserAvatar from './UserAvatar';
import './leaderboard.css';

const Leaderboard = ({ users }) => {
    return (
        <div className="leaderboard">
            <h2>Leaderboard</h2>
            <ul>
                {users.map(user => (
                    <li key={user.id} className="leaderboard-item">
                        <UserAvatar url={user.profilePicture} />
                        <span className="username">{user.username}</span>
                        <span className="score">{user.score}</span>
                    </li>
                ))}
            </ul>
        </div>
    );
};

export default Leaderboard;