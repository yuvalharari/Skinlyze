// NAV - toggle mobile menu
function toggleMenu() {
  document.getElementById('navLinks').classList.toggle('open');
}

// Close menu when clicking outside
document.addEventListener('click', function (e) {
  const nav = document.getElementById('navLinks');
  const hamburger = document.getElementById('hamburger');
  if (nav && hamburger && !nav.contains(e.target) && !hamburger.contains(e.target)) {
    nav.classList.remove('open');
  }
});


// FILE UPLOAD
const imageInput = document.getElementById('imageInput');
const uploadZone = document.getElementById('uploadZone');
const uploadPreview = document.getElementById('uploadPreview');
const previewImg = document.getElementById('previewImg');
const previewName = document.getElementById('previewName');
const analyzeBtn = document.getElementById('analyzeBtn');

let cropper = null;

if (imageInput) {
  imageInput.addEventListener('change', handleFile);
}

if (uploadZone) {
  uploadZone.addEventListener('dragover', function (e) {
    e.preventDefault();
    uploadZone.classList.add('dragover');
  });

  uploadZone.addEventListener('dragleave', function () {
    uploadZone.classList.remove('dragover');
  });

  uploadZone.addEventListener('drop', function (e) {
    e.preventDefault();
    uploadZone.classList.remove('dragover');
    if (e.dataTransfer.files[0]) {
      imageInput.files = e.dataTransfer.files;
      handleFile();
    }
  });
}

function handleFile() {
  const file = imageInput.files[0];
  if (!file) return;

  const url = URL.createObjectURL(file);
  previewImg.src = url;
  previewName.textContent = file.name;
  uploadPreview.style.display = 'block';
  analyzeBtn.disabled = false;

  if (cropper) {
    cropper.destroy();
    cropper = null;
  }

  previewImg.onload = function () {
    cropper = new Cropper(previewImg, {
      aspectRatio: 4 / 3,
      viewMode: 1,
      autoCropArea: 1.0,
      movable: true,
      zoomable: true,
      rotatable: false,
      scalable: false,
    });
  };
}


// ANALYSIS
async function runAnalysis() {
  document.getElementById('uploadCard').style.display = 'none';
  document.getElementById('loadingState').style.display = 'block';
  document.getElementById('resultsSection').style.display = 'none';

  const formData = new FormData();

  if (cropper) {
    const cropData = cropper.getData();
    const imageData = cropper.getImageData();

    const isFullImage =
      Math.abs(cropData.x) < 5 &&
      Math.abs(cropData.y) < 5 &&
      Math.abs(cropData.width - imageData.naturalWidth) < 5 &&
      Math.abs(cropData.height - imageData.naturalHeight) < 5;

    if (isFullImage) {
      const file = imageInput.files[0];
      formData.append('image', file);
    } else {
      const canvas = cropper.getCroppedCanvas({ maxWidth: 1024, maxHeight: 1024 });
      await new Promise((resolve) => {
        canvas.toBlob(function (blob) {
          formData.append('image', blob, 'cropped.jpg');
          resolve();
        }, 'image/jpeg', 0.95);
      });
    }
  } else {
    const file = imageInput.files[0];
    if (!file) return;
    formData.append('image', file);
  }

  try {
    const res = await fetch('/analyze', { method: 'POST', body: formData });
    const data = await res.json();

    if (data.error === 'image_quality') {
      document.getElementById('loadingState').style.display = 'none';
      document.getElementById('uploadCard').style.display = 'block';
      showImageError(data.message);
      return;
    }

    showResults(data);
  } catch (err) {
    alert('Analysis failed. Please try again.');
    resetAnalysis();
  }
}


// SHOW RESULTS WITH ANIMATIONS
function showResults(data) {
  document.getElementById('loadingState').style.display = 'none';

  const section = document.getElementById('resultsSection');
  section.style.opacity = '0';
  section.style.transform = 'translateY(24px)';
  section.style.display = 'block';

  const isSuspicious = data.prediction === 1;



  // Scan ring + title
  const scanRing = document.getElementById('scanRing');
  const scanIcon = document.getElementById('scanIcon');
  const resultTitle = document.getElementById('resultTitle');
  const resultSub = document.getElementById('resultSub');

  if (scanRing) {
    scanRing.className = 'scan-ring ' + (isSuspicious ? 'suspicious' : 'safe');
    if (isSuspicious) {
      scanIcon.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" width="30" height="30"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" /></svg>';
      resultTitle.textContent = 'Suspicious Lesion';
      resultSub.textContent = 'Please consult a dermatologist';
    } else {
      scanIcon.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" width="30" height="30"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" /></svg>';
      resultTitle.textContent = 'Not Suspicious';
      resultSub.textContent = 'Continue monitoring regularly';
    }
  }

  // ABC grid
  const abcGrid = document.getElementById('abcGrid');
  const insightSection = document.getElementById('insightSection');

  if (isSuspicious && data.abc_scores) {
    abcGrid.style.display = 'flex';
    const abc = data.abc_scores;
    setABC('a', abc.A);
    setABC('b', abc.B);
    setABC('c', abc.C);
  } else {
    abcGrid.style.display = 'none';
  }

  // Insight
  if (insightSection) {
    const insightBody = document.getElementById('insightBody');
    if (isSuspicious && data.insight) {
      insightSection.style.display = 'block';
      insightBody.textContent = data.insight;
    } else if (!isSuspicious) {
      insightSection.style.display = 'block';
      insightBody.textContent = 'The lesion does not appear suspicious based on the AI model\'s assessment. Continue monitoring for any changes in size, shape, or color, and consult a dermatologist if you notice any evolution over time.';
    } else {
      insightSection.style.display = 'none';
    }
  }

  // Animate section in
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      section.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
      section.style.opacity = '1';
      section.style.transform = 'translateY(0)';
    });
  });

  // Animate ABC rows + bars
  if (isSuspicious && data.abc_scores) {
    ['A', 'B', 'C'].forEach((letter, i) => {
      const row = document.getElementById('abcRow' + letter);
      if (!row) return;
      row.style.opacity = '0';
      row.style.transform = 'translateX(-16px)';
      setTimeout(() => {
        row.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
        row.style.opacity = '1';
        row.style.transform = 'translateX(0)';
        const bar = document.getElementById('abcBar' + letter);
        const scoreObj = data.abc_scores[letter];
        if (bar && scoreObj) {
          const pct = Math.round((scoreObj.score || 0) * 100);
          setTimeout(() => { bar.style.width = pct + '%'; }, 80);
          const val = document.getElementById('abcVal' + letter);
          if (val) val.textContent = pct + '%';
        }
      }, 500 + i * 180);
    });

    // Animate insight after ABC
    if (insightSection) {
      insightSection.style.opacity = '0';
      insightSection.style.transform = 'translateY(10px)';
      setTimeout(() => {
        insightSection.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
        insightSection.style.opacity = '1';
        insightSection.style.transform = 'translateY(0)';
      }, 1100);
    }
  }
}

function setABC(letter, obj) {
  if (!obj) return;
  const upper = letter.toUpperCase();
  const explain = document.getElementById(letter + 'Explain');
  if (explain) explain.textContent = obj.explanation || '';
  const val = document.getElementById('abcVal' + upper);
  if (val) val.textContent = Math.round((obj.score || 0) * 100) + '%';
}

function resetAnalysis() {
  document.getElementById('uploadCard').style.display = 'block';
  document.getElementById('loadingState').style.display = 'none';
  document.getElementById('resultsSection').style.display = 'none';
  document.getElementById('uploadPreview').style.display = 'none';
  document.getElementById('analyzeBtn').disabled = true;
  imageInput.value = '';
  document.getElementById('imageErrorBox').style.display = 'none';
  document.getElementById('imageErrorMsg').textContent = '';

  // Reset bars
  ['A', 'B', 'C'].forEach(l => {
    const bar = document.getElementById('abcBar' + l);
    if (bar) bar.style.width = '0%';
    const val = document.getElementById('abcVal' + l);
    if (val) val.textContent = '0%';
  });

  if (cropper) {
    cropper.destroy();
    cropper = null;
  }
}


// LIVE STATS
function animateCounter(element, target, duration = 1500) {
  let start = 0;
  const increment = target / (duration / 16);
  const timer = setInterval(() => {
    start += increment;
    if (start >= target) {
      element.textContent = target.toLocaleString();
      clearInterval(timer);
    } else {
      element.textContent = Math.floor(start).toLocaleString();
    }
  }, 16);
}

async function loadStats() {
  try {
    const res = await fetch('/stats');
    const data = await res.json();

    const total = document.getElementById('statTotal');
    const suspicious = document.getElementById('statSuspicious');
    const safe = document.getElementById('statSafe');

    if (total) animateCounter(total, data.total);
    if (suspicious) animateCounter(suspicious, data.suspicious);
    if (safe) animateCounter(safe, data.safe);
  } catch (err) {
    console.error('Stats error:', err);
  }
}

if (document.getElementById('statTotal')) {
  loadStats();
}


// IMAGE QUALITY ERROR
function showImageError(message) {
  document.getElementById('imageErrorMsg').textContent = message;
  document.getElementById('imageErrorBox').style.display = 'flex';
}


// STEPS SLIDER
(function() {
  const track = document.getElementById('stepsTrack');
  if (!track) return;

  let current = 0;
  const total = 4;
  const fill = document.getElementById('stepsProgressFill');
  const dots = document.querySelectorAll('.steps-dot');
  let progress = 0;
  let interval;

  function goTo(index) {
    current = (index + total) % total;
    track.style.transform = 'translateX(-' + (current * 100) + '%)';
    dots.forEach((d, i) => d.classList.toggle('active', i === current));
    resetProgress();
  }

  function resetProgress() {
    clearInterval(interval);
    progress = 0;
    fill.style.transition = 'none';
    fill.style.width = '0%';
    setTimeout(() => {
      fill.style.transition = 'width 0.1s linear';
      interval = setInterval(() => {
        progress += 100 / 70;
        if (progress >= 100) {
          goTo(current + 1);
          return;
        }
        fill.style.width = progress + '%';
      }, 100);
    }, 50);
  }

  window.stepsGoTo = goTo;
  document.getElementById('stepsPrev').onclick = () => goTo(current - 1);
  document.getElementById('stepsNext').onclick = () => goTo(current + 1);
  resetProgress();
})();