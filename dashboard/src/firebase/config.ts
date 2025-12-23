// Import the functions you need from the SDKs you need
import { initializeApp } from "firebase/app";
import { getDatabase } from "firebase/database";
import { getAuth, GoogleAuthProvider } from "firebase/auth";
import { getFirestore } from "firebase/firestore";

// Your web app's Firebase configuration
const firebaseConfig = {
    apiKey: "AIzaSyB2vfWNmg5UB_BmXab5B0PMdfErYLNtZr4",
    authDomain: "gluco-watch.firebaseapp.com",
    databaseURL: "https://gluco-watch-default-rtdb.europe-west1.firebasedatabase.app",
    projectId: "gluco-watch",
    storageBucket: "gluco-watch.firebasestorage.app",
    messagingSenderId: "690390587166",
    appId: "1:690390587166:web:2812e8435aa398575d1b0f"
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);

// Initialize Realtime Database
export const database = getDatabase(app);

// Initialize Firebase Authentication
export const auth = getAuth(app);

// Initialize Google Auth Provider
export const googleProvider = new GoogleAuthProvider();

// Initialize Firestore
export const db = getFirestore(app);

export default app;
