# Leaderboard App

## Overview
The Leaderboard App is a web application that displays a leaderboard of users along with their profile pictures. Users can also upload their photos to enhance their profiles. This application is built using React and TypeScript.

## Features
- Displays a leaderboard with user profile pictures.
- Allows users to upload their photos.
- Responsive design for a seamless user experience.

## Project Structure
```
leaderboard-app
├── src
│   ├── components
│   │   ├── Leaderboard.tsx        # Displays the leaderboard with user avatars
│   │   ├── UserAvatar.tsx         # Renders user avatars from profile picture URLs
│   │   └── UploadPhotoButton.tsx   # Button for uploading user photos
│   ├── pages
│   │   └── Dashboard.tsx           # Main dashboard integrating leaderboard and upload functionalities
│   ├── hooks
│   │   └── useUpload.ts            # Custom hook for handling file uploads
│   ├── services
│   │   └── api.ts                  # Handles API calls for fetching and uploading user data
│   ├── styles
│   │   └── leaderboard.css          # Styles for the leaderboard and components
│   ├── types
│   │   └── index.ts                 # Type definitions for user profiles and uploads
│   └── index.tsx                   # Entry point of the application
├── public
│   └── index.html                  # Main HTML file for the application
├── package.json                    # Configuration file for npm dependencies and scripts
├── tsconfig.json                   # TypeScript configuration file
└── README.md                       # Project documentation
```

## Installation
1. Clone the repository:
   ```
   git clone <repository-url>
   ```
2. Navigate to the project directory:
   ```
   cd leaderboard-app
   ```
3. Install the dependencies:
   ```
   npm install
   ```

## Usage
To start the application, run:
```
npm start
```
This will launch the app in your default web browser.

## Contributing
Contributions are welcome! Please open an issue or submit a pull request for any enhancements or bug fixes.

## License
This project is licensed under the MIT License.