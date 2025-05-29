import csv
import io
from flask import Blueprint, request, redirect, url_for, flash, Response, render_template, send_file
from flask_login import login_required, current_user
from dateutil.parser import parse
from db_utils import db_connection, get_placeholder
from utils import correggi_orario

export_bp = Blueprint('export', __name__)

@export_bp.route("/esporta_csv", methods=["GET", "POST"])
@login_required
def esporta_csv():
    from flask import current_app
    current_app.config['WTF_CSRF_ENABLED'] = False
    
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
        
    if request.method == "GET":
        return render_template("esporta_opzioni.html")
    
    
    tipo_export = request.form.get("tipo_export", "tutte")
    
    with db_connection() as conn:
        cursor = conn.cursor()
        lezioni = []
        filename = "lezioni.csv"
        
        if tipo_export == "tutte":
            query = "SELECT * FROM lezioni"
            cursor.execute(query)
            lezioni = cursor.fetchall()
            filename = "tutte_lezioni.csv"
            
        elif tipo_export == "settimana":
            data_settimana = request.form.get("data_settimana")
            if not data_settimana:
                flash("❌ Seleziona una data valida", "danger")
                return redirect(url_for("export.esporta_csv"))
                
            placeholder = get_placeholder()
            query = f"""
                SELECT * FROM lezioni 
                WHERE extract_year_week(data) = extract_year_week({placeholder})
            """
            cursor.execute(query, (data_settimana,))
            lezioni = cursor.fetchall()
            filename = f"lezioni_settimana_{data_settimana}.csv"
            
        elif tipo_export == "mese":
            mese = request.form.get("mese")
            if not mese:
                flash("❌ Seleziona un mese valido", "danger")
                return redirect(url_for("export.esporta_csv"))
                
            placeholder = get_placeholder()
            query = f"""
                SELECT * FROM lezioni 
                WHERE extract_year_month(data) = {placeholder}
            """
            cursor.execute(query, (mese,))
            lezioni = cursor.fetchall()
            filename = f"lezioni_mese_{mese}.csv"
            
        elif tipo_export == "anno":
            anno = request.form.get("anno")
            if not anno:
                flash("❌ Seleziona un anno valido", "danger")
                return redirect(url_for("export.esporta_csv"))
                
            placeholder = get_placeholder()
            query = f"""
                SELECT * FROM lezioni 
                WHERE extract_year(data) = {placeholder}
            """
            cursor.execute(query, (anno,))
            lezioni = cursor.fetchall()
            filename = f"lezioni_anno_{anno}.csv"
            
        elif tipo_export == "giorni_liberi":
            tipo_periodo = request.form.get("tipo_periodo", "settimana")
            
            fasce_orarie = [f"{h:02d}:00" for h in range(8, 21)]
            giorni = []
            
            if tipo_periodo == "settimana":
                data_settimana = request.form.get("data_settimana_libera")
                if not data_settimana:
                    flash("❌ Seleziona una data valida", "danger")
                    return redirect(url_for("export.esporta_csv"))
                
                placeholder = get_placeholder()
                query_date = f"""
                    WITH RECURSIVE dates(date) AS (
                        SELECT (TO_DATE({placeholder}, 'YYYY-MM-DD') - INTERVAL '7 days' + 
                               ((1 - EXTRACT(DOW FROM TO_DATE({placeholder}, 'YYYY-MM-DD')))::INTEGER % 7) * INTERVAL '1 day')::DATE
                        UNION ALL
                        SELECT (date + INTERVAL '1 day')::DATE
                        FROM dates
                        WHERE date < (TO_DATE({placeholder}, 'YYYY-MM-DD') - INTERVAL '7 days' + 
                                     ((7 - EXTRACT(DOW FROM TO_DATE({placeholder}, 'YYYY-MM-DD')))::INTEGER % 7) * INTERVAL '1 day')::DATE
                    )
                    SELECT date::TEXT FROM dates
                    WHERE extract_weekday(date::TEXT) NOT IN ('0', '6')  -- Esclude sabato e domenica
                    ORDER BY date
                """
                cursor.execute(query_date, (data_settimana, data_settimana, data_settimana, data_settimana))
                giorni = cursor.fetchall()
                filename = f"ore_libere_settimana_{data_settimana}.csv"
                
            elif tipo_periodo == "mese":
                mese = request.form.get("mese_libero")
                if not mese:
                    flash("❌ Seleziona un mese valido", "danger")
                    return redirect(url_for("export.esporta_csv"))
                
                anno, mese_num = mese.split('-')
                placeholder = get_placeholder()
                query_date = f"""
                    WITH RECURSIVE dates(date) AS (
                        SELECT TO_DATE({placeholder}, 'YYYY-MM-DD')::DATE
                        UNION ALL
                        SELECT (date + INTERVAL '1 day')::DATE
                        FROM dates
                        WHERE extract_year_month(date::TEXT) = {placeholder}
                    )
                    SELECT date::TEXT FROM dates
                    WHERE extract_weekday(date::TEXT) NOT IN ('0', '6')  -- Esclude sabato e domenica
                    ORDER BY date
                """
                cursor.execute(query_date, (f"{mese}-01", mese))
                giorni = cursor.fetchall()
                filename = f"ore_libere_mese_{mese}.csv"
                
            elif tipo_periodo == "anno":
                anno = request.form.get("anno_libero")
                if not anno:
                    flash("❌ Seleziona un anno valido", "danger")
                    return redirect(url_for("export.esporta_csv"))
                
                placeholder = get_placeholder()
                query_date = f"""
                    WITH RECURSIVE dates(date) AS (
                        SELECT TO_DATE({placeholder} || '-01-01', 'YYYY-MM-DD')::DATE
                        UNION ALL
                        SELECT (date + INTERVAL '1 day')::DATE
                        FROM dates
                        WHERE extract_year(date::TEXT) = {placeholder}
                    )
                    SELECT date::TEXT FROM dates
                    WHERE extract_weekday(date::TEXT) NOT IN ('0', '6')  -- Esclude sabato e domenica
                    ORDER BY date
                """
                cursor.execute(query_date, (anno, anno))
                giorni = cursor.fetchall()
                filename = f"ore_libere_anno_{anno}.csv"
            else:
                flash("❌ Tipo di periodo non valido", "danger")
                return redirect(url_for("export.esporta_csv"))
            
            header = "data,giorno_settimana,ore_libere\n"
            rows = []
            
            for giorno in giorni:
                data = giorno["date"]
                placeholder = get_placeholder()
                giorno_settimana = ["Domenica", "Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato"][int(cursor.execute(f"SELECT extract_weekday({placeholder})", (data,)).fetchone()[0])]
                
                ore_libere = []
                for ora in fasce_orarie:
                    placeholder = get_placeholder()
                    query_lezioni = f"""
                        SELECT COUNT(*) FROM lezioni 
                        WHERE data = {placeholder} 
                        AND (
                            (ora_inizio <= {placeholder} AND ora_fine > {placeholder}) OR
                            (ora_inizio < {placeholder} AND ora_fine >= {placeholder}) OR
                            (ora_inizio >= {placeholder} AND ora_fine <= {placeholder})
                        )
                    """
                    cursor.execute(query_lezioni, (data, ora, ora, ora, ora, ora, ora))
                    count = cursor.fetchone()[0]
                    
                    if count == 0:  # Solo le ore libere
                        ore_libere.append(ora)
                
                if ore_libere:  # Solo se ci sono ore libere
                    rows.append(f"{data},{giorno_settimana},{', '.join(ore_libere)}")
            
            output = header + "\n".join(rows)
            
            csv_buffer = io.StringIO()
            csv_buffer.write(output)
            csv_buffer.seek(0)
            
            return Response(
                csv_buffer.getvalue(),
                mimetype="text/csv",
                headers={"Content-Disposition": f"attachment;filename={filename}"}
            )
        
        elif tipo_export == "formato_ridotto":
            cursor.execute("SELECT id_corso, data FROM lezioni ORDER BY data")
            lezioni_ridotte = cursor.fetchall()
            
            corsi_dict = {}
            cursor.execute("SELECT id_corso, nome, cliente FROM corsi")
            for corso in cursor.fetchall():
                try:
                    cliente = corso["cliente"] if corso["cliente"] else ""
                except (KeyError, IndexError):
                    cliente = ""
                    
                corsi_dict[corso["id_corso"]] = {
                    "nome": corso["nome"],
                    "cliente": cliente
                }
            
            header = "data,id_corso,nome_corso,cliente\n"
            rows = []
            for lezione in lezioni_ridotte:
                id_corso = lezione["id_corso"]
                corso_info = corsi_dict.get(id_corso, {"nome": id_corso, "cliente": ""})
                rows.append(f'{lezione["data"]},{id_corso},{corso_info["nome"]},{corso_info["cliente"]}')
            
            output = header + "\n".join(rows)
            
            csv_buffer = io.StringIO()
            csv_buffer.write(output)
            csv_buffer.seek(0)
            
            return Response(
                csv_buffer.getvalue(),
                mimetype="text/csv",
                headers={"Content-Disposition": f"attachment;filename=lezioni_formato_ridotto.csv"}
            )
        
        corsi_clienti = {}
        cursor.execute("SELECT id_corso, cliente FROM corsi")
        for corso in cursor.fetchall():
            try:
                corsi_clienti[corso["id_corso"]] = corso["cliente"] if corso["cliente"] else ""
            except (KeyError, IndexError):
                corsi_clienti[corso["id_corso"]] = ""
            
        header = "id_corso,materia,data,ora_inizio,ora_fine,luogo,compenso_orario,stato,fatturato,mese_fatturato,ore_fatturate,cliente\n"
        rows = []
        for lezione in lezioni:
            cliente = corsi_clienti[lezione["id_corso"]] if lezione["id_corso"] in corsi_clienti else ""
            rows.append(
                f'{lezione["id_corso"]},{lezione["materia"]},{lezione["data"]},{lezione["ora_inizio"]},'
                f'{lezione["ora_fine"]},{lezione["luogo"]},{lezione["compenso_orario"]},'
                f'{lezione["stato"]},{lezione["fatturato"]},{lezione["mese_fatturato"] or ""},'
                f'{lezione.get("ore_fatturate", 0)},{cliente}'
            )
        output = header + "\n".join(rows)
        
        csv_buffer = io.StringIO()
        csv_buffer.write(output)
        csv_buffer.seek(0)
        
        response = Response(
            csv_buffer.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment;filename={filename}"}
        )
        return response


@export_bp.route("/importa_csv", methods=["GET", "POST"])
@login_required
def importa_csv():
    from flask import current_app
    current_app.config['WTF_CSRF_ENABLED'] = False
    
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
        
    if request.method == "POST":
        file = request.files.get("file")
        if not file or file.filename == "":
            flash("❌ Nessun file selezionato!", "danger")
            filter_params = {k: v for k, v in request.args.items() if v}
            return redirect(url_for("lezioni.dashboard", **filter_params))

        if not file.filename.endswith(".csv"):
            flash("❌ Formato non supportato. Carica un file CSV.", "danger")
            filter_params = {k: v for k, v in request.args.items() if v}
            return redirect(url_for("lezioni.dashboard", **filter_params))

        try:
            stream = file.stream.read().decode("utf-8").splitlines()
            csv_reader = csv.DictReader(stream)

            colonne_minime = [
                "id_corso", "materia", "data", "ora_inizio", "ora_fine"
            ]
            colonne_opzionali = [
                "luogo", "compenso_orario", "stato", "fatturato", "mese_fatturato", "ore_fatturate"
            ]
            fieldnames = csv_reader.fieldnames or []
            colonne_mancanti = [col for col in colonne_minime if col not in fieldnames]
            if colonne_mancanti:
                flash(f"❌ Colonne essenziali mancanti nel CSV: {', '.join(colonne_mancanti)}", "danger")
                filter_params = {k: v for k, v in request.args.items() if v}
                return redirect(url_for("lezioni.dashboard", **filter_params))
                
            colonne_opzionali_mancanti = [col for col in colonne_opzionali if col not in fieldnames]
            if colonne_opzionali_mancanti:
                flash(f"ℹ️ Colonne opzionali mancanti (verranno usati valori predefiniti): {', '.join(colonne_opzionali_mancanti)}", "info")

            with db_connection() as conn:
                cursor = conn.cursor()

                for row in csv_reader:
                    try:
                        id_corso = row.get("id_corso", "").strip()
                        materia = row.get("materia", "").strip()
                        data_originale = row.get("data", "").strip()
                        ora_inizio = correggi_orario(row.get("ora_inizio", "").strip())
                        ora_fine = correggi_orario(row.get("ora_fine", "").strip())
                        
                        if not ora_inizio or not ora_fine:
                            flash(f"❌ Orario non valido per la lezione '{materia}'", "danger")
                            continue
                            
                        luogo = row.get("luogo", "").strip() if "luogo" in fieldnames else ""
                        compenso_orario = row.get("compenso_orario", "0").strip() if "compenso_orario" in fieldnames else "0"
                        stato = row.get("stato", "Pianificato").strip() if "stato" in fieldnames else "Pianificato"
                        cliente = row.get("cliente", "").strip() if "cliente" in fieldnames else ""
                        
                        try:
                            fatturato_val = int(row.get("fatturato", "0").strip()) if "fatturato" in fieldnames else 0
                        except ValueError:
                            fatturato_val = 0
                            
                        mese_fatturato = row.get("mese_fatturato", "").strip() if "mese_fatturato" in fieldnames else None
                        if mese_fatturato == "":
                            mese_fatturato = None
                            
                        placeholder = get_placeholder()
                        cursor.execute(f"""
                            SELECT calcola_ore({placeholder}, {placeholder}) as ore_totali
                        """, (ora_inizio, ora_fine))
                        ore_totali = cursor.fetchone()["ore_totali"]
                        
                        ore_fatturate = ore_totali if fatturato_val > 0 else 0.0
                        
                        data_convertita = parse(data_originale).strftime("%Y-%m-%d") if data_originale else None
                        
                        placeholder = get_placeholder()
                        cursor.execute(f"SELECT COUNT(*) FROM corsi WHERE id_corso = {placeholder}", (id_corso,))
                        if cursor.fetchone()[0] == 0:
                            nome_corso = f"Corso {id_corso}"
                            placeholder = get_placeholder()
                            cursor.execute(f"INSERT INTO corsi (id_corso, nome, cliente) VALUES ({placeholder}, {placeholder}, {placeholder})", 
                                          (id_corso, nome_corso, cliente))
                            
                        placeholder = get_placeholder()
                        cursor.execute(f"""
                            INSERT INTO lezioni (id_corso, materia, data, ora_inizio, ora_fine, luogo, compenso_orario, stato, fatturato, mese_fatturato, ore_fatturate)
                            VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
                        """, (
                            id_corso,
                            materia,
                            data_convertita,
                            ora_inizio,
                            ora_fine,
                            luogo,
                            float(compenso_orario.replace(',', '.')) if compenso_orario else 0.0,
                            stato,
                            fatturato_val,
                            mese_fatturato,
                            ore_fatturate
                        ))
                        
                        print(f"✅ Lezione importata: {materia} - {data_convertita} ({ora_inizio}-{ora_fine})")

                    except Exception as e:
                        print(f"❌ Errore durante l'inserimento della riga: {row} → {str(e)}")
                        flash("❌ Errore nell'importazione di una riga. Controlla il file CSV.", "danger")

                conn.commit()

            flash("✅ CSV importato con successo!", "success")

        except Exception as e:
            flash(f"❌ Errore durante la lettura del file: {str(e)}", "danger")

        filter_params = {k: v for k, v in request.args.items() if v}
        return redirect(url_for("lezioni.dashboard", **filter_params))

    return render_template("importa_csv.html")


@export_bp.route("/segnala_fatturato", methods=["POST"])
@login_required
def segnala_fatturato():
    corso = request.form.get("corso")
    mese_fatturato = request.form.get("mese_fatturato")

    if not corso or not mese_fatturato:
        flash("Errore: Devi selezionare un corso e un mese!", "danger")
        return redirect(url_for("compenso"))

    try:
        with db_connection() as conn:
            cursor = conn.cursor()
            placeholder = get_placeholder()
            cursor.execute(f"""
                UPDATE lezioni
                SET fatturato = 1, mese_fatturato = {placeholder}
                WHERE id_corso = {placeholder} AND stato = 'Completato' AND fatturato = 0
            """, (mese_fatturato, corso))
            conn.commit()
        flash("✅ Lezioni marcate come fatturate con successo!", "success")
    except Exception as e:
        flash(f"❌ Errore durante l'aggiornamento: {str(e)}", "danger")

    return redirect(url_for("compenso", corso=corso))
