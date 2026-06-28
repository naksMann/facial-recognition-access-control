// Import the functions you need from the SDKs you need
  import { initializeApp } from "https://www.gstatic.com/firebasejs/12.4.0/firebase-app.js";
  import{getAuth, createUserWithEmailAndPassword, signInWithEmailAndPassword} from "https://www.gstatic.com/firebasejs/12.4.0/firebase-auth.js";
  import{getFirestore, setDoc, doc, getDocs, collection, query, where, addDoc} from "https://www.gstatic.com/firebasejs/12.4.0/firebase-firestore.js"

  // Firebase configuration
const firebaseConfig = {
    apiKey: "AIzaSyAyZIESMLPZrR12UKiHksS-W_hJYSA_NHg",
    authDomain: "facial-recorgnition-data.firebaseapp.com",
    projectId: "facial-recorgnition-data",
    storageBucket: "facial-recorgnition-data.appspot.com",
    messagingSenderId: "194417054581",
    appId: "1:194417054581:web:65862d22c36c2f94eef93c"
};

// Initialize Firebase (non-module) and expose firebaseReady + helper
(function() {
  const cfg = {
    apiKey: "AIzaSyAyZIESMLPZrR12UKiHksS-W_hJYSA_NHg",
    authDomain: "facial-recorgnition-data.firebaseapp.com",
    projectId: "facial-recorgnition-data",
    storageBucket: "facial-recorgnition-data.appspot.com",
    messagingSenderId: "194417054581",
    appId: "1:194417054581:web:65862d22c36c2f94eef93c"
  };

  // Promise that resolves when firebase is available & initialized
  window.firebaseReady = new Promise((resolve) => {
    const tryInit = () => {
      if (typeof firebase !== 'undefined') {
        try {
          if (!firebase.apps.length) firebase.initializeApp(cfg);
          // optional: set auth state listener
          firebase.auth().onAuthStateChanged(() => {});
          console.log('Firebase initialized (client).');
        } catch (e) {
          console.warn('Firebase init error:', e);
        }
        resolve(true);
        return true;
      }
      return false;
    };

    if (!tryInit()) {
      const iv = setInterval(() => {
        if (tryInit()) {
          clearInterval(iv);
        }
      }, 100);
      // fail-safe timeout
      setTimeout(() => { clearInterval(iv); resolve(false); }, 5000);
    }
  });

  // Helper to get ID token (waits for firebaseReady)
  window.getFirebaseToken = async function(forceRefresh = true) {
    const ready = await window.firebaseReady;
    if (!ready) throw new Error('Firebase client not available');
    const user = firebase.auth().currentUser;
    if (!user) return null;
    return await user.getIdToken(forceRefresh);
  };

})();

function showMessage(message, divId){
    var messageDiv=document.getElementById(divId);
    messageDiv.style.display="block";
    messageDiv.innerHTML=message;
    messageDiv.style.opacity=1;
    setTimeout(function(){
      messageDiv.style.opacity=0;
    }, 5000);
  }

  const signUp=document.getElementById('submitSignUp');
  if (signUp) signUp.addEventListener('click',(event)=>{
    event.preventDefault();
    const email=document.getElementById('rEmail').value;
    const password=document.getElementById('rPassword').value;
    const firstName=document.getElementById('fName').value;
    const lastName=document.getElementById('lName').value;

    const auth=getAuth();
    const db=getFirestore();

    createUserWithEmailAndPassword(auth, email, password)
    .then((userCredential)=>{
      const user=userCredential.user;
      const userData={
        email: email,
        firstName:firstName,
        lastName:lastName
      };
      showMessage('Account Created Successfully', 'signUpMessage');
      const docRef=doc(db, "Users", user.uid); // use user.uid
      setDoc(docRef,userData)
      .then(()=>{
        window.location.href='capture.html';
      })
      .catch((error)=>{
        console.error("error writing document", error);
      });
    })
    .catch((error)=>{
      const errorCode=error.code;
      if(errorCode=='auth/email-already-in-use'){
        showMessage('Email Address Already Exists !!!', 'signUpMessage');
      }
      else{
        showMessage('unable to create User','signUpMessage');
      }
    })
  });
  const signIn=document.getElementById('submitSignIn');
  if (signIn) signIn.addEventListener('click',(event)=>{
    event.preventDefault();
    const email=document.getElementById('email').value;
    const password=document.getElementById('password').value;
    const auth=getAuth();
    const db=getFirestore();

    signInWithEmailAndPassword(auth, email, password)
    .then((userCredential)=>{
      showMessage('Signed In Successfully', 'signInMessage');
      const user=userCredential.user;
      // log successful login
      addDoc(collection(db,'AccessLogs'),{
        userId:user.uid,
        email: email,
        eventType:'login',
        success:true,
        createdAt: Date.now()
      });
      localStorage.setItem('loggedInUser', user.uid);
      window.location.href='verify.html';
    })
    .catch((error)=>{
      const errorCode = error.code;
      (async ()=>{
        let resolvedUser = null;
        try{
          const usersQ = query(collection(db,'Users'), where('email','==', email));
          const snaps = await getDocs(usersQ);
          snaps.forEach(d=>{ if(!resolvedUser) resolvedUser = { id:d.id, ...d.data() }; });
        }catch(_){ }
        const success=false;
        const eventType='login';
        const userId = resolvedUser ? resolvedUser.id : 'unknown';
        const displayName = resolvedUser ? `${resolvedUser.firstName||''} ${resolvedUser.lastName||''}`.trim() : 'Unknown';
        try{
          await addDoc(collection(db,'AccessLogs'),{
            userId,
            email: email || 'unknown',
            eventType,
            success,
            reason: errorCode,
            displayName,
            createdAt: new Date().toISOString()
          });
        }catch(_){ }
      })();
      if (
        errorCode === 'auth/wrong-password' ||
        errorCode === 'auth/invalid-credential' ||
        errorCode === 'auth/user-not-found' ||
        errorCode === 'auth/invalid-email'
      ) {
        showMessage('Incorrect Email or Password', 'signInMessage');
      } else {
        showMessage('Unable to sign in', 'signInMessage');
      }
    })
  })

