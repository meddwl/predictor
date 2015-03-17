# -*- coding: utf-8 -*-
from pony.orm import *
from collections import defaultdict

import time
import os
import sys

db = Database("sqlite", "database.sqlite", create_db=True)


class Users(db.Entity):
    id = PrimaryKey(int, auto=True)
    email = Required(str, 128, unique=True)
    tasks = Set("Tasks")


class Tasks(db.Entity):
    id = PrimaryKey(int, auto=True)
    user = Optional(Users)
    chemicals = Set("Chemicals")
    status = Required(int, default=0)
    create_date = Required(int)


class Chemicals(db.Entity):
    id = PrimaryKey(int, auto=True)
    status = Required(int, default=0)
    temperature = Optional(float)
    solvents = Set("Solventsets")
    task = Required(Tasks)
    structure = Required("Structures")
    results = Set("Results")
    models = Set("Models")


class Structures(db.Entity):
    id = PrimaryKey(int, auto=True)
    key = Optional(str)
    structure = Required(str)
    chemicals = Set(Chemicals)


class Results(db.Entity):
    id = PrimaryKey(int, auto=True)
    chemical = Required(Chemicals)
    attrib = Required(str)
    value = Required(float)
    model = Required("Models")


class AppDomains(db.Entity):
    id = PrimaryKey(int, auto=True)
    hash = Required(str)
    model = Set("Models")


class Models(db.Entity):
    id = PrimaryKey(int, auto=True)
    name = Required(unicode)
    chemicals = Set(Chemicals)
    results = Set(Results)
    is_reaction = Required(bool, default=False)
    app_domains = Set("AppDomains")


class Solvents(db.Entity):
    id = PrimaryKey(int, auto=True)
    smiles = Required(str, unique=True)
    name = Required(str, unique=True)
    solventsets = Set("Solventsets")


class Solventsets(db.Entity):
    amount = Required(float)
    solvent = Required(Solvents)
    chemical = Required(Chemicals)


sql_debug(True)
db.generate_mapping(create_tables=True)

class PredictorDataBase:
    @db_session
    def get_tasks(self, status=None):
        if status:
            tasks = select(x for x in Tasks if x.status == status)
        else:
            tasks = select(x for x in Tasks)    # удалить в продакшене

        arr = []
        for t in tasks:
            arr.append(dict(id=t.id,
                            status=t.status))
        return arr




    @db_session
    def insert_task(self, email=None):
        '''
        функция добавляет в таблицу новую задачу
        :param email: мыло если есть.
        :return:
        '''
        if email:
            user = Users.get(email=email)
            if not user:
                user = Users(email=email)
        else:
            user = None

        task = Tasks(user=user, create_date=int(time.time()))
        commit()
        return task.id

    @db_session
    def get_task_status(self, task_id):
        '''
        функция возвращает задачу по заданному ID
        :param task_id: ID добавляемой задачи
        :return: status
        '''
        t = Tasks.get(id=task_id)
        if t:
            return t.status
        return None

    @db_session
    def update_task_status(self, task_id, status):
        '''
        функция обновляет статус у задачи
        :param task_id: ID задачи (str)
        :param status: устанавливаемое значение (int)
        :return: True|False
        '''
        t = Tasks.get(id=task_id)
        if t:
            t.status = status
            return True
        else:
            return False

    @db_session
    def insert_reaction(self, task_id, reaction_structure, solvent=None, temperature=None, structurekey=None):
        '''
        функция добавляет в таблицу новую реакцию с заданными параметрами
        :param task_id(str): ID задачи
        :param reaction_structure(str): Структура реакции в формате mrv
        :param solvent(str): Растворитель
        :param temperature(str): Температура
        :return: reaction id or False
        '''
        print('insert_reaction->task_id='+str(task_id))
        t = Tasks.get(id=task_id)
        if t:
            structure = Structures(structure=reaction_structure)
            commit()
            chem = Chemicals(task=t, structure=structure, temperature=temperature)
            commit()
            if solvent:
                for k, v in solvent.items():
                    db_solvent = Solvents.get(id=k)
                    if db_solvent:
                        Solventsets(amount=v, solvent=db_solvent, chemical=chem)

            return chem.id
        else:
            print('TASK NOT FOUND!!!')
            return False

    @db_session
    def get_reaction_structure(self, reaction_id):
        '''
        функция возвращает структуру реакции по заданному ID
        :param id(str): ID реакции
        :return: структура реакции
        '''
        c = Chemicals.get(id=reaction_id)
        if c:
            return c.structure.structure
        else:
            return None

    @db_session
    def get_reaction(self, reaction_id):
        '''
        функция возвращает структуру реакции по заданному ID
        :param id(str): ID реакции
        :return: поля реакции
        '''
        c = Chemicals.get(id=reaction_id)
        if c:
            return dict(structure=c.structure.structure,
                        temperature=c.temperature,
                        models={y.id: y.name for y in c.models},
                        solvents={y.id: y.amount for y in c.solvents})
        else:
            return None

    @db_session
    def get_reactions(self):
        '''
        функция возвращает структуру реакции по заданному ID
        :param id(str): ID реакции
        :return: поля реакции
        '''
        arr = []
        for r in select(x for x in Chemicals):
            arr.append(dict(reaction_id=r.id,
                            task_id=r.task.id,
                            structure=r.structure.structure,
                            temperature=r.temperature,
                            models={m.id: m.name for m in r.models},
                            solvents={s.id: s.amount for s in r.solvents}))
        return arr


    @db_session
    def update_reaction_structure(self, reaction_id, structure):
        '''
        функция возвращает структуру реакции по заданному ID
        :param id(str): ID реакции
        :param structure(str): структура реакции
        :return: true, false
        '''
        c = Chemicals.get(id=reaction_id)
        if c:
            c.structure.structure = structure
            return True
        else:
            return False

    @db_session
    def update_reaction_conditions(self, reaction_id, temperature=None, solvent=None, model=None):
        '''
        функция записывает в базу ввведенные пользователем данные для моделирования
        :return:
        '''
        c = Chemicals.get(id=reaction_id)
        if c:
            if temperature:
                c.temperature = temperature
            if solvent:
                for x in c.solvents:  # очистка старых растворителей.
                    x.delete()
                for k, v in solvent.items():  # новые данные по растворителям
                    db_solvent = Solvents.get(id=k)
                    if db_solvent:
                        Solventsets(amount=v, solvent=db_solvent, chemical=c)
            if model:
                for k in model:
                    m = Models.get(id=k)
                    if m:
                        m.chemicals = c
            return True
        else:
            return False


    @db_session
    def update_reaction_result(self, reaction_id, model_id, param, value):
        '''
        функция записывает в базу ввведенные пользователем данные для моделирования
        :return:
        '''
        reaction = Chemicals.get(id=reaction_id)
        model = Models.get(id=model_id)
        if reaction and model:
            Results(chemical=reaction, model=model, attrib=param, value=value)


    @db_session
    def get_reactions_by_task(self, task_id):
        '''
        функция возвращает список реакций для заданной задачи
        :param task_id: ID задачи
        :return: список реакций (ID, solvent, temperature, models)
        '''
        arr = []
        t = Tasks.get(id=task_id)
        if t:
            for x in t.chemicals:
                arr.append(dict(reaction_id=x.id,
                                temperature=x.temperature,
                                models={m.id: m.name for m in x.models},
                                solvents={s.id: s.amount for s in x.solvents},
                                errors={}))
            return arr
        else:
            return None


    @db_session
    def get_results_by_task(self, task_id):
        '''
        функция возвращает результаты моделирования для заданной задачи
        :param task_id(str): ID задачи
        :return: Результаты моделирования
        '''

########################

        t = Tasks.get(id=task_id)
        if t:
            for reaction in t.chemicals:
                for _m in select(m for m in Models):
                    result = Results(chemical=reaction, model=_m, attrib='logC', value=111)

###########################

        out = []
        t = Tasks.get(id=task_id)
        if t:
            for r in t.chemicals:
                result_arr = []
                for res in r.results:
                    result_arr.append(dict(
                                    model=res.model.name,
                                    param=res.attrib,
                                    value=res.value))
                out.append(dict(reaction_id=r.id, results=result_arr))
        return out


    @db_session
    def get_solvents(self):
        '''
        функция возвращает список растворителей из базы
        :return: список растворителей
        '''
        query = select((x.id,x.name) for x in Solvents)
        return [{'id': x, 'name': y} for x, y in query]

    @db_session
    def get_models(self):
        '''
        функция возвращает список доступных моделей
        :return: список моделей
        '''
        query = select((x.id,x.name, x.is_reaction) for x in Models)
        return [{'id': x, 'name': y, 'is_reaction': z} for x, y, z in query]


    @db_session
    def insert_model(self, name, is_reaction, reaction_hash=None):
        model = Models(name=name, is_reaction=is_reaction)
        if reaction_hash:
            domain = AppDomains(hash=reaction_hash, model=model)
        else:
            domain = None
        commit()
        return model.id



basedir = os.path.abspath(os.path.dirname(__file__))


# загрузим данные
@db_session
def import_solvents():
    file = open(os.path.join(os.path.dirname(__file__), "import_data/solvents.txt"), "r")
    for _line in file.readlines():
        try:
            arr = _line.split("\t")
            sm = arr[0]
            n = arr[1].strip(' \t\n\r')
            s = Solvents.get(smiles=sm)
            if not s:
                  Solvents(smiles=sm, name=n)
        except:
            print('import_solvents->', sys.exc_info()[0])
            pass
    file.close()


@db_session
def import_models():
    file = open(os.path.join(os.path.dirname(__file__), "import_data/models.txt"), "r")
    for _line in file.readlines():
        try:
            arr = _line.split("\t")
            _name = arr[0]
            _hash = arr[1].strip(' \t\n\r')
            _flag = arr[2].strip(' \t\n\r')
            model = Models.get(name=_name)
            hash = AppDomains.get(hash=_hash)
            if not model and not hash:
                hash = AppDomains(hash=_hash)
                model = Models(name=_name)
                if _flag == '1':
                    model.is_reaction = True
                hash.model = model

        except:
            print('import_solvents->', sys.exc_info()[0])
            pass
    file.close()


import_solvents()
import_models()


