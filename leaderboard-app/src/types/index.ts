export interface UserProfile {
    id: string;
    username: string;
    profilePictureUrl: string;
}

export interface UploadedPhoto {
    id: string;
    userId: string;
    photoUrl: string;
    uploadDate: Date;
}