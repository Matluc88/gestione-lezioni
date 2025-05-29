document.addEventListener('DOMContentLoaded', function() {
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
        console.error('Il tuo browser non supporta il riconoscimento vocale.');
        document.getElementById('voiceSearchButton').style.display = 'none';
        return;
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const recognition = new SpeechRecognition();
    recognition.lang = 'it-IT';
    recognition.continuous = false;
    recognition.interimResults = false;

    const voiceSearchButton = document.getElementById('voiceSearchButton');
    const voiceSearchModal = document.getElementById('voiceSearchModal');
    const voiceSearchResults = document.getElementById('voiceSearchResults');
    const voiceSearchStatus = document.getElementById('voiceSearchStatus');
    const closeVoiceModal = document.getElementById('closeVoiceModal');

    voiceSearchButton.addEventListener('click', function() {
        voiceSearchResults.innerHTML = '';
        voiceSearchStatus.textContent = 'Pronto per ascoltare. Pronuncia una data (es. "15 maggio 2023")';
        voiceSearchModal.style.display = 'block';
    });

    closeVoiceModal.addEventListener('click', function() {
        voiceSearchModal.style.display = 'none';
        recognition.stop();
    });

    document.getElementById('startVoiceSearch').addEventListener('click', function() {
        voiceSearchStatus.textContent = 'In ascolto...';
        recognition.start();
    });

    recognition.onresult = function(event) {
        const transcript = event.results[0][0].transcript.toLowerCase();
        voiceSearchStatus.textContent = `Hai detto: "${transcript}"`;
        
        searchLessonsByVoice(transcript);
    };

    recognition.onerror = function(event) {
        voiceSearchStatus.textContent = `Errore: ${event.error}`;
    };

    recognition.onend = function() {
        voiceSearchStatus.textContent += ' (Ascolto terminato)';
    };

    function searchLessonsByVoice(transcript) {
        voiceSearchResults.innerHTML = '<div class="text-center"><div class="spinner-border" role="status"><span class="visually-hidden">Caricamento...</span></div></div>';
        
        fetch('/cerca_lezioni_vocale', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ query: transcript }),
        })
        .then(response => response.json())
        .then(data => {
            if (data.success && data.lezioni.length > 0) {
                let resultsHtml = '<div class="list-group">';
                data.lezioni.forEach(lezione => {
                    const dataFormattata = new Date(lezione.data).toLocaleDateString('it-IT', {
                        weekday: 'long',
                        year: 'numeric',
                        month: 'long',
                        day: 'numeric'
                    });
                    
                    resultsHtml += `
                        <div class="list-group-item">
                            <div class="d-flex w-100 justify-content-between">
                                <h5 class="mb-1">${lezione.materia}</h5>
                                <small>${dataFormattata}</small>
                            </div>
                            <p class="mb-1">
                                <strong>Orario:</strong> ${lezione.ora_inizio} - ${lezione.ora_fine}<br>
                                <strong>Corso:</strong> ${lezione.id_corso}<br>
                                <strong>Luogo:</strong> ${lezione.luogo}
                            </p>
                            <a href="/modifica_lezione/${lezione.id}" class="btn btn-sm btn-primary mt-2">Dettagli</a>
                        </div>
                    `;
                });
                resultsHtml += '</div>';
                voiceSearchResults.innerHTML = resultsHtml;
            } else {
                voiceSearchResults.innerHTML = '<div class="alert alert-info">Nessuna lezione trovata per la data specificata.</div>';
            }
        })
        .catch(error => {
            console.error('Errore durante la ricerca:', error);
            voiceSearchResults.innerHTML = '<div class="alert alert-danger">Si è verificato un errore durante la ricerca.</div>';
        });
    }
});
