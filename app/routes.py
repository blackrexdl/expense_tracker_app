import csv, io, os
from datetime import date, datetime, timedelta
from flask import render_template, request, redirect, url_for, flash, session, abort, jsonify, Response
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

DEFAULTS = [('Salary','income'),('Freelance','income'),('Food','expense'),('Transport','expense'),('Rent','expense'),('Utilities','expense'),('Health','expense'),('Other','expense')]

def register_routes(app):
    db = app.get_db; required = app.login_required
    def due_recurring(uid):
        rows=db().execute('SELECT * FROM recurring_transactions WHERE user_id=? AND active=1 AND next_date<=?',(uid,date.today().isoformat())).fetchall()
        for r in rows:
            db().execute('INSERT INTO transactions(user_id,category_id,amount,kind,note,transaction_date) VALUES(?,?,?,?,?,?)',(uid,r['category_id'],r['amount'],r['kind'],r['note'],r['next_date']))
            days=7 if r['frequency']=='weekly' else 30
            next_day=(datetime.strptime(r['next_date'],'%Y-%m-%d').date()+timedelta(days=days)).isoformat()
            db().execute('UPDATE recurring_transactions SET next_date=? WHERE id=?',(next_day,r['id']))
        if rows: db().commit()
    @app.context_processor
    def inject_user(): return {'current_user': session.get('username'), 'today': date.today().isoformat()}
    @app.route('/register', methods=['GET','POST'])
    def register():
        if request.method == 'POST':
            username=request.form.get('username','').strip(); password=request.form.get('password','')
            if len(username)<3 or len(password)<8: flash('Username must have 3 characters and password 8.', 'error')
            elif db().execute('SELECT 1 FROM users WHERE username=?',(username,)).fetchone(): flash('Username is already taken.', 'error')
            else:
                cur=db().execute('INSERT INTO users(username,password_hash) VALUES(?,?)',(username,generate_password_hash(password)))
                for name,kind in DEFAULTS: db().execute('INSERT INTO categories(user_id,name,kind) VALUES(?,?,?)',(cur.lastrowid,name,kind))
                db().commit(); flash('Account created. Please sign in.', 'success'); return redirect(url_for('login'))
        return render_template('auth.html', mode='register')
    @app.route('/login', methods=['GET','POST'])
    def login():
        if request.method == 'POST':
            user=db().execute('SELECT * FROM users WHERE username=?',(request.form.get('username','').strip(),)).fetchone()
            if user and check_password_hash(user['password_hash'],request.form.get('password','')):
                session.clear(); session['user_id']=user['id']; session['username']=user['username']; return redirect(url_for('dashboard'))
            flash('Invalid username or password.', 'error')
        return render_template('auth.html', mode='login')
    @app.get('/logout')
    def logout(): session.clear(); return redirect(url_for('login'))
    @app.get('/')
    @required
    def dashboard():
        uid=session['user_id']; due_recurring(uid); params=[uid]; where=' WHERE t.user_id=?'
        kind=request.args.get('kind',''); category=request.args.get('category',''); start=request.args.get('start',''); end=request.args.get('end',''); q=request.args.get('q','').strip()
        if kind in ('income','expense'): where+=' AND t.kind=?'; params.append(kind)
        if category.isdigit(): where+=' AND t.category_id=?'; params.append(int(category))
        if q: where += ' AND (t.note LIKE ? OR CAST(t.amount AS TEXT) LIKE ?)'; params.extend([f'%{q}%',f'%{q}%'])
        for value,op in ((start,'>='),(end,'<=')):
            if value:
                try: datetime.strptime(value,'%Y-%m-%d'); where+=f' AND t.transaction_date {op} ?'; params.append(value)
                except ValueError: flash('Invalid date filter ignored.', 'error')
        categories=db().execute('SELECT * FROM categories WHERE user_id=? ORDER BY kind,name',(uid,)).fetchall()
        tx=db().execute('SELECT t.*, c.name category FROM transactions t JOIN categories c ON c.id=t.category_id'+where+' ORDER BY transaction_date DESC,t.id DESC',params).fetchall()
        totals=db().execute("SELECT kind, COALESCE(SUM(amount),0) total FROM transactions t"+where+' GROUP BY kind',params).fetchall(); total={r['kind']:r['total'] for r in totals}
        month=date.today().strftime('%Y-%m'); alerts=db().execute("SELECT c.name, b.amount, COALESCE(SUM(t.amount),0) spent FROM budgets b JOIN categories c ON c.id=b.category_id LEFT JOIN transactions t ON t.category_id=b.category_id AND t.kind='expense' AND substr(t.transaction_date,1,7)=b.month WHERE b.user_id=? AND b.month=? GROUP BY b.id",(uid,month)).fetchall()
        return render_template('dashboard.html', categories=categories, transactions=tx, income=total.get('income',0), expense=total.get('expense',0), alerts=alerts, filters=request.args)
    def valid_tx(form, uid):
        try: amount=round(float(form.get('amount','')),2); assert amount>0
        except: return None, 'Amount must be a positive number.'
        kind=form.get('kind'); cat=form.get('category_id',''); dt=form.get('transaction_date','')
        if kind not in ('income','expense') or not cat.isdigit(): return None, 'Choose a valid type and category.'
        try: datetime.strptime(dt,'%Y-%m-%d')
        except: return None, 'Choose a valid date.'
        category=db().execute('SELECT id FROM categories WHERE id=? AND user_id=? AND kind=?',(cat,uid,kind)).fetchone()
        if not category: return None, 'That category does not match the transaction type.'
        return (amount,kind,int(cat),dt,form.get('note','').strip()[:250]), None
    @app.post('/transactions')
    @required
    def add_transaction():
        data,error=valid_tx(request.form,session['user_id'])
        if error: flash(error,'error')
        else:
            receipt=request.files.get('receipt'); path=None
            if receipt and receipt.filename:
                name=secure_filename(receipt.filename)
                if name.rsplit('.',1)[-1].lower() not in {'png','jpg','jpeg','pdf'}: flash('Receipt must be PNG, JPG, or PDF.','error'); return redirect(url_for('dashboard'))
                os.makedirs(os.path.join(app.static_folder,'uploads'),exist_ok=True); path=f'uploads/{session["user_id"]}_{datetime.now().timestamp():.0f}_{name}'; receipt.save(os.path.join(app.static_folder,path))
            db().execute('INSERT INTO transactions(user_id,amount,kind,category_id,transaction_date,note,receipt_path) VALUES(?,?,?,?,?,?,?)',(session['user_id'],data[0],data[1],data[2],data[3],data[4],path)); db().commit(); flash('Transaction saved.','success')
        return redirect(url_for('dashboard'))
    @app.post('/transactions/<int:tid>/delete')
    @required
    def delete_transaction(tid):
        db().execute('DELETE FROM transactions WHERE id=? AND user_id=?',(tid,session['user_id'])); db().commit(); flash('Transaction deleted.','success'); return redirect(url_for('dashboard'))
    @app.route('/transactions/<int:tid>/edit', methods=['GET','POST'])
    @required
    def edit_transaction(tid):
        uid=session['user_id']; tx=db().execute('SELECT * FROM transactions WHERE id=? AND user_id=?',(tid,uid)).fetchone()
        if not tx: abort(404)
        if request.method=='POST':
            data,error=valid_tx(request.form,uid)
            if error: flash(error,'error')
            else:
                db().execute('UPDATE transactions SET amount=?,kind=?,category_id=?,transaction_date=?,note=? WHERE id=? AND user_id=?',(*data,tid,uid)); db().commit(); flash('Transaction updated.','success'); return redirect(url_for('dashboard'))
        categories=db().execute('SELECT * FROM categories WHERE user_id=? ORDER BY kind,name',(uid,)).fetchall()
        return render_template('edit.html', transaction=tx, categories=categories)
    @app.post('/categories')
    @required
    def add_category():
        name=request.form.get('name','').strip()[:40]; kind=request.form.get('kind')
        if not name or kind not in ('income','expense'): flash('Enter a category name and type.','error')
        else:
            try: db().execute('INSERT INTO categories(user_id,name,kind) VALUES(?,?,?)',(session['user_id'],name,kind)); db().commit(); flash('Category added.','success')
            except: flash('This category already exists.','error')
        return redirect(url_for('dashboard'))
    @app.post('/categories/<int:cid>/delete')
    @required
    def delete_category(cid):
        used=db().execute('SELECT 1 FROM transactions WHERE category_id=? AND user_id=?',(cid,session['user_id'])).fetchone()
        if used: flash('Cannot delete a category that has transactions.','error')
        else: db().execute('DELETE FROM categories WHERE id=? AND user_id=?',(cid,session['user_id'])); db().commit(); flash('Category deleted.','success')
        return redirect(url_for('dashboard'))
    @app.post('/categories/<int:cid>/edit')
    @required
    def edit_category(cid):
        name=request.form.get('name','').strip()[:40]
        if not name: flash('Category name is required.','error')
        else:
            try: db().execute('UPDATE categories SET name=? WHERE id=? AND user_id=?',(name,cid,session['user_id'])); db().commit(); flash('Category updated.','success')
            except: flash('A category with that name already exists.','error')
        return redirect(url_for('manage'))
    @app.post('/budgets')
    @required
    def budget():
        try: amount=float(request.form['amount']); assert amount>0; datetime.strptime(request.form['month']+'-01','%Y-%m-%d')
            
        except: flash('Enter a positive budget and valid month.','error'); return redirect(url_for('dashboard'))
        cat=request.form.get('category_id',''); row=db().execute("SELECT id FROM categories WHERE id=? AND user_id=? AND kind='expense'",(cat,session['user_id'])).fetchone()
        if not row: flash('Choose an expense category.','error')
        else: db().execute('INSERT INTO budgets(user_id,category_id,month,amount) VALUES(?,?,?,?) ON CONFLICT(user_id,category_id,month) DO UPDATE SET amount=excluded.amount',(session['user_id'],cat,request.form['month'],amount)); db().commit(); flash('Budget saved.','success')
        return redirect(url_for('dashboard'))
    @app.post('/budgets/<int:bid>/delete')
    @required
    def delete_budget(bid): db().execute('DELETE FROM budgets WHERE id=? AND user_id=?',(bid,session['user_id'])); db().commit(); flash('Budget removed.','success'); return redirect(url_for('dashboard'))
    @app.get('/export/transactions.csv')
    @required
    def export_csv():
        rows=db().execute('SELECT t.transaction_date,t.kind,c.name,t.amount,t.note FROM transactions t JOIN categories c ON c.id=t.category_id WHERE t.user_id=? ORDER BY t.transaction_date DESC',(session['user_id'],)).fetchall(); out=io.StringIO(); writer=csv.writer(out); writer.writerow(['Date','Type','Category','Amount','Note']); writer.writerows(rows)
        return Response(out.getvalue(),mimetype='text/csv',headers={'Content-Disposition':'attachment; filename=transactions.csv'})
    @app.get('/export/report.pdf')
    @required
    def export_pdf():
        rows=db().execute('SELECT transaction_date,kind,amount,note FROM transactions WHERE user_id=? ORDER BY transaction_date DESC LIMIT 35',(session['user_id'],)).fetchall()
        lines=['ExpenseTrack report']+[f"{r['transaction_date']}  {r['kind']}  {r['amount']:.2f}  {r['note'][:40]}" for r in rows]
        def esc(s): return s.replace('\\','\\\\').replace('(','\\(').replace(')','\\)')
        stream='BT /F1 14 Tf 50 780 Td '
        for i,line in enumerate(lines): stream += ('' if i==0 else '0 -18 Td ') + f'({esc(line)}) Tj '
        stream+='ET'; objects=['<< /Type /Catalog /Pages 2 0 R >>','<< /Type /Pages /Kids [3 0 R] /Count 1 >>','<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>',f'<< /Length {len(stream)} >>\nstream\n{stream}\nendstream','<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>']
        pdf='%PDF-1.4\n'; offsets=[0]
        for i,obj in enumerate(objects,1): offsets.append(len(pdf)); pdf+=f'{i} 0 obj\n{obj}\nendobj\n'
        xref=len(pdf); pdf+='xref\n0 6\n0000000000 65535 f \n'+''.join(f'{o:010d} 00000 n \n' for o in offsets[1:])+f'trailer << /Size 6 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF'
        return Response(pdf,mimetype='application/pdf',headers={'Content-Disposition':'attachment; filename=expense-report.pdf'})
    @app.get('/api/categories')
    @required
    def category_summary():
        rows=db().execute("SELECT c.name, COALESCE(SUM(t.amount),0) total FROM categories c LEFT JOIN transactions t ON t.category_id=c.id WHERE c.user_id=? AND c.kind='expense' GROUP BY c.id ORDER BY total DESC",(session['user_id'],)).fetchall(); return jsonify([dict(r) for r in rows])
    @app.get('/manage')
    @required
    def manage():
        uid=session['user_id']; month=date.today().strftime('%Y-%m')
        categories=db().execute('SELECT * FROM categories WHERE user_id=? ORDER BY kind,name',(uid,)).fetchall()
        budgets=db().execute("SELECT b.*,c.name,COALESCE(SUM(t.amount),0) spent FROM budgets b JOIN categories c ON c.id=b.category_id LEFT JOIN transactions t ON t.category_id=b.category_id AND t.kind='expense' AND substr(t.transaction_date,1,7)=b.month WHERE b.user_id=? AND b.month=? GROUP BY b.id",(uid,month)).fetchall()
        recurring=db().execute('SELECT r.*,c.name FROM recurring_transactions r JOIN categories c ON c.id=r.category_id WHERE r.user_id=? ORDER BY r.next_date',(uid,)).fetchall()
        return render_template('manage.html',categories=categories,budgets=budgets,recurring=recurring,month=month)
    @app.post('/recurring')
    @required
    def add_recurring():
        data,error=valid_tx(request.form,session['user_id'])
        frequency=request.form.get('frequency')
        if error or frequency not in ('weekly','monthly'): flash(error or 'Choose a valid frequency.','error')
        else: db().execute('INSERT INTO recurring_transactions(user_id,category_id,amount,kind,note,frequency,next_date) VALUES(?,?,?,?,?,?,?)',(session['user_id'],data[2],data[0],data[1],data[4],frequency,data[3])); db().commit(); flash('Recurring transaction added.','success')
        return redirect(url_for('manage'))
    @app.post('/recurring/<int:rid>/delete')
    @required
    def delete_recurring(rid): db().execute('DELETE FROM recurring_transactions WHERE id=? AND user_id=?',(rid,session['user_id'])); db().commit(); flash('Recurring transaction removed.','success'); return redirect(url_for('manage'))
    @app.route('/settings',methods=['GET','POST'])
    @required
    def settings():
        uid=session['user_id']
        if request.method=='POST':
            action=request.form.get('action')
            if action=='password':
                u=db().execute('SELECT password_hash FROM users WHERE id=?',(uid,)).fetchone()
                if not check_password_hash(u['password_hash'],request.form.get('current_password','')) or len(request.form.get('new_password',''))<8: flash('Current password is incorrect or new password is too short.','error')
                else: db().execute('UPDATE users SET password_hash=? WHERE id=?',(generate_password_hash(request.form['new_password']),uid)); db().commit(); flash('Password changed.','success')
            else:
                currency=request.form.get('currency','₹')[:3]; theme=request.form.get('theme','dark'); budget=request.form.get('monthly_budget') or None
                db().execute('INSERT INTO settings(user_id,currency,theme,monthly_budget) VALUES(?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET currency=excluded.currency,theme=excluded.theme,monthly_budget=excluded.monthly_budget',(uid,currency,theme,budget)); db().commit(); flash('Settings saved.','success')
            return redirect(url_for('settings'))
        setting=db().execute('SELECT * FROM settings WHERE user_id=?',(uid,)).fetchone()
        return render_template('settings.html',setting=setting)
    @app.get('/api/summary')
    @required
    def summary():
        period=request.args.get('period','monthly'); days={'daily':7,'weekly':8,'monthly':12,'yearly':5}.get(period,12); uid=session['user_id']; rows=[]
        for i in range(days-1,-1,-1):
            d=date.today()-timedelta(days=i) if period=='daily' else date.today().replace(day=1)
            if period=='weekly': d=date.today()-timedelta(days=7*i)
            if period=='monthly': d=(date.today().replace(day=1)-timedelta(days=1)).replace(day=1) if i else date.today().replace(day=1)
            if period=='monthly':
                d=date.today().replace(day=1)
                for _ in range(i): d=(d-timedelta(days=1)).replace(day=1)
            if period=='yearly': d=date(date.today().year-i,1,1)
            key=d.strftime('%Y-%m-%d') if period=='daily' else (d.strftime('%Y-W%W') if period=='weekly' else (d.strftime('%Y-%m') if period=='monthly' else d.strftime('%Y')))
            if period=='daily': clause="transaction_date=?"; arg=d.isoformat()
            elif period=='weekly': clause="strftime('%Y-W%W',transaction_date)=?"; arg=key
            elif period=='monthly': clause="substr(transaction_date,1,7)=?"; arg=key
            else: clause="substr(transaction_date,1,4)=?"; arg=key
            vals=db().execute(f"SELECT kind,COALESCE(SUM(amount),0) s FROM transactions WHERE user_id=? AND {clause} GROUP BY kind",(uid,arg)).fetchall(); x={v['kind']:v['s'] for v in vals}; rows.append({'label':key,'income':x.get('income',0),'expense':x.get('expense',0)})
        return jsonify(rows)
    @app.get('/report/monthly')
    @required
    def monthly_report():
        month=request.args.get('month', date.today().strftime('%Y-%m'))
        try: datetime.strptime(month+'-01','%Y-%m-%d')
        except ValueError: abort(400)
        rows=db().execute("SELECT c.name,t.kind,SUM(t.amount) amount FROM transactions t JOIN categories c ON c.id=t.category_id WHERE t.user_id=? AND substr(t.transaction_date,1,7)=? GROUP BY c.id,t.kind ORDER BY t.kind,c.name",(session['user_id'],month)).fetchall()
        return render_template('report.html', month=month, rows=rows)
