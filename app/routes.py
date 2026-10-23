from datetime import date, datetime, timedelta
from flask import render_template, request, redirect, url_for, flash, session, abort, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

DEFAULTS = [('Salary','income'),('Freelance','income'),('Food','expense'),('Transport','expense'),('Rent','expense'),('Utilities','expense'),('Health','expense'),('Other','expense')]

def register_routes(app):
    db = app.get_db; required = app.login_required
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
        uid=session['user_id']; params=[uid]; where=' WHERE t.user_id=?'
        kind=request.args.get('kind',''); category=request.args.get('category',''); start=request.args.get('start',''); end=request.args.get('end','')
        if kind in ('income','expense'): where+=' AND t.kind=?'; params.append(kind)
        if category.isdigit(): where+=' AND t.category_id=?'; params.append(int(category))
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
        else: db().execute('INSERT INTO transactions(user_id,amount,kind,category_id,transaction_date,note) VALUES(?,?,?,?,?,?)',(session['user_id'],data[0],data[1],data[2],data[3],data[4])); db().commit(); flash('Transaction saved.','success')
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
    @app.post('/budgets')
    @required
    def budget():
        try: amount=float(request.form['amount']); assert amount>0; datetime.strptime(request.form['month']+'-01','%Y-%m-%d')
            
        except: flash('Enter a positive budget and valid month.','error'); return redirect(url_for('dashboard'))
        cat=request.form.get('category_id',''); row=db().execute("SELECT id FROM categories WHERE id=? AND user_id=? AND kind='expense'",(cat,session['user_id'])).fetchone()
        if not row: flash('Choose an expense category.','error')
        else: db().execute('INSERT INTO budgets(user_id,category_id,month,amount) VALUES(?,?,?,?) ON CONFLICT(user_id,category_id,month) DO UPDATE SET amount=excluded.amount',(session['user_id'],cat,request.form['month'],amount)); db().commit(); flash('Budget saved.','success')
        return redirect(url_for('dashboard'))
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
