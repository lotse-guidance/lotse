import asyncio
import logging
import sys
from typing import List, Any, Optional, Dict

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.websockets import WebSocket, WebSocketDisconnect

from .guidance_engine import socket_manager
from .guidance_engine.lotse_engine import LotseEngine
from .guidance_engine.socket_manager import get_connection_manager, ConnectionManager
from ..suggestion import SuggestionModel

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.Logger('catch_all')


class GuidanceAPI(FastAPI):
    def __init__(self, **extra: Any):
        super().__init__(**extra)
        self.lotse_engine = None
        self.action_task = None
        self.strategies_task = None

        self.guidance_loop_timeout = 2
        self.inference_loop_timeout = 30

    def get_engine(self) -> LotseEngine:
        return self.lotse_engine

    # every two seconds, evaluate all conditional actions and potentially generate new suggestions
    async def evaluate_actions(self, manager=get_connection_manager()):
        try:
            retract = self.lotse_engine.suggestions_to_retract()
            print(f"got suggestions to retract: {retract}")
            for suggestion in retract:
                print('hi')
                suggestion.interaction = 'retract'
                suggestion.action.retract(app.lotse_engine.current_state, app.lotse_engine.last_delta, suggestion)
                await manager.broadcast(suggestion)

            print('generating suggestions')
            suggestions = self.lotse_engine.generate_suggestions()
            print(f"got new suggestions to broadcast: {suggestions}")
            for suggestion in suggestions:
                print(suggestion)
                await manager.broadcast(suggestion)
        except:
            logging.exception("Could not evaluate actions")

    # every two seconds, evaluate all conditional actions and potentially generate new suggestions
    async def evaluate_actions_continuously(self):
        while True:
            print('-----------------------------------------------------')
            print('generating next update')

            # broadcast new guidance
            await self.evaluate_actions()
            await asyncio.sleep(self.guidance_loop_timeout)

    # every 30 seconds, evaluate all strategies
    async def evaluate_strategies_continously(self):
        while True:
            print('updating strategies periodically')
            self.evaluate_strategies()
            await asyncio.sleep(self.inference_loop_timeout)

    def evaluate_strategies(self):
        try:
            if not self.lotse_engine.current_state:
                return
            self.lotse_engine.applicable_strategies = self.lotse_engine.get_applicable_strategies()
            self.lotse_engine.generate_conditional_actions()
        except:
            logging.exception("Could not evaluate actions")

    def setup_engine(self, path: str, initial_context, meta='meta.yaml', guidance_loop_timeout=2, inference_loop_timeout=30):
        self.lotse_engine = LotseEngine(path, initial_context, meta)
        self.lotse_engine.applicable_strategies = self.lotse_engine.strategies
        self.guidance_loop_timeout = guidance_loop_timeout
        self.inference_loop_timeout = inference_loop_timeout
        print(f"got {len(self.lotse_engine.applicable_strategies)} applicable strats")
        self.lotse_engine.generate_conditional_actions()
        return self

    def start(self):
        if not self.lotse_engine:
            raise Exception('You must initialize your engine by calling setup_engine() first.')
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()

        def handle_exception(loop, context):
            msg = context.get("exception", context["message"])
            logging.error(f"Caught exception: {msg}")

        loop.set_exception_handler(handle_exception)

        self.strategies_task = loop.create_task(self.evaluate_strategies_continously())
        self.action_task = loop.create_task(self.evaluate_actions_continuously())
        if not loop.is_running():
            loop.run_forever()

    def stop(self):
        if not self.lotse_engine:
            raise Exception('You must initialize your engine by calling setup_engine() first.')
        self.strategies_task.cancel()
        self.action_task.cancel()

    def update_state(self, key, value):
        self.lotse_engine.current_state.__dict__.update({key: value})


app = GuidanceAPI()

origins = [
    "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
def handle_annotation_error(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "error": str(exc)
        }
    )


@app.get('/start',
         tags=['Engine Configuration'],
         description="Starts the guidance engine. You can either call `start()` from python, immediately when setting \
          up the engine, or later once your visualization components have been initialized. To activate or deactivate \
           individual guidance strategies, consider adding flags or other filter mechanisms to the context vector.")
async def start_engine():
    app.start()


@app.get('/stop',
         tags=['Engine Configuration'],
         description="Stops the guidance engine temporarily. To activate or deactivate individual guidance strategies, \
          consider adding flags or other filter mechanisms to the context vector.")
def stop_engine():
    app.stop()


@app.get("/suggestions",
         tags=['Guidance Interactions'],
         description="Retrieve all suggestions currently made by the engine. Typically, new suggestions will be \
          transmitted via the websocket. However, (re-)fetching them via REST might become necessary, e.g., after \
           refreshing the page."
         )
def get_guidance_suggestions() -> List[SuggestionModel]:
    return app.lotse_engine.suggestions


@app.websocket("/channels/{client_id}")
async def chatroom_ws(client_id: str,
                      websocket: WebSocket,
                      manager: ConnectionManager = Depends(socket_manager.get_connection_manager)):
    if client_id is None:
        raise ValueError("Please specify a Client ID")
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json(mode="text")
            try:
                # we don't really do anything with messages we get from the websocket!
                pass
            except Exception as e:
                logger.error("got error while processing message", exc_info=True)
    except WebSocketDisconnect:
        print("got disconnect exception")
        await manager.disconnect(websocket)


class StateUpdate(BaseModel):
    re_evaluate_actions: Optional[bool] = Field(True,
                                                description="Whether to immediately re-evaluate all actions (True) or wait until the next scheduled check (False)")
    re_evaluate_strategies: Optional[bool] = Field(False,
                                                   description="Whether to immediately re-evaluate all strategies (True) or wait until the next scheduled check (False)")


class StateVectorUpdate(StateUpdate):
    updates: Dict[str, Any] = Field(description="A dictionary of key-value pairs to update in the state vector")


@app.post('/state/update',
          tags=['State Vector Manipulation'],
          description="Updates the state vector by applying all key-value pairs specified in the `updates` field. \
                      If you need more complex updates than setting values directly, use `update_with_callback`"
          )
async def update_state(update: StateVectorUpdate):
    app.lotse_engine.last_delta = update.updates
    for key, value in update.updates.items():
        app.update_state(key, value)
    if update.re_evaluate_strategies is True:
        app.evaluate_strategies()
    if update.re_evaluate_actions is True:
        await app.evaluate_actions()


class StateVectorUpdateWithCallback(StateUpdate):
    callback: str = Field(description="The name of the callback to execute as specified in the stat vector yaml file.")
    params: Dict[str, Any] = Field(description="Key-value pairs to be passed to the callback as named arguments.")


@app.post('/state/update_with_callback',
          tags=['State Vector Manipulation'],
          description="Instead of simply applying new key-value pairs to the state vector, this method executes a \
                      callback on the context vector. The name of the callback specified here must have been declared \
                      in the state vector yaml file."
          )
async def update_with_callback(update: StateVectorUpdateWithCallback):
    callback = getattr(app.lotse_engine.current_state, update.callback)
    app.lotse_engine.last_delta = callback(**update.params)
    if update.re_evaluate_strategies is True:
        app.evaluate_strategies()
    if update.re_evaluate_actions is True:
        await app.evaluate_actions()


@app.post('/reject',
          tags=['Guidance Interactions'],
          response_model=None,
          description="Finds the suggestion instance in the engine by matching the IDs and rejects the found instance, \
                      calling its reject method as defined in the yaml file. Finally, the suggestion is removed from \
                      the engine's list of current suggestions.")
def reject_suggestion(rejected_suggestion: SuggestionModel):
    engine_suggestion: SuggestionModel = next(
        sugg for sugg in app.lotse_engine.suggestions if sugg.suggestion.id == rejected_suggestion.suggestion.id)
    engine_suggestion.action.reject(engine_suggestion, app.lotse_engine.current_state, app.lotse_engine.last_delta)
    app.lotse_engine.suggestions = list(
        filter(lambda s: s.suggestion.id != engine_suggestion.suggestion.id, app.lotse_engine.suggestions))


@app.post('/accept',
          tags=['Guidance Interactions'],
          response_model=None,
          description="Finds the suggestion instance in the engine by matching the IDs and rejects the found instance, \
                      calling its reject method as defined in the yaml file. Finally, the suggestion is removed from \
                      the engine's list of current suggestions.")
def accept_suggestion(accepted_suggestion: SuggestionModel):
    engine_suggestion: SuggestionModel = next(
        sugg for sugg in app.lotse_engine.suggestions if sugg.suggestion.id == accepted_suggestion.suggestion.id)
    engine_suggestion.action.accept(engine_suggestion, app.lotse_engine.current_state, app.lotse_engine.last_delta)
    app.lotse_engine.suggestions = list(
        filter(lambda s: s.suggestion.id != engine_suggestion.suggestion.id, app.lotse_engine.suggestions))


@app.post('/preview_start',
          tags=['Guidance Interactions'],
          response_model=None,
          description="Finds the suggestion instance in the engine by matching the IDs and calls `preview_start` on \
          the found instance, if it is defined in the action's yaml file.")
def preview_suggestion(previewed: SuggestionModel):
    engine_suggestion = next(
        sugg for sugg in app.lotse_engine.suggestions if sugg.suggestion.id == previewed.suggestion.id)
    engine_suggestion.action.preview_start(engine_suggestion, app.lotse_engine.current_state, app.lotse_engine.last_delta)


@app.post('/preview_end',
          tags=['Guidance Interactions'],
          response_model=None,
          description="Finds the suggestion instance in the engine by matching the IDs and calls `preview_start` on \
          the found instance, if it is defined in the action's yaml file.")
def end_preview_for_suggestion(suggestion: SuggestionModel):
    engine_suggestion = next(
        sugg for sugg in app.lotse_engine.suggestions if sugg.suggestion.id == suggestion.suggestion.id)
    engine_suggestion.action.preview_end(engine_suggestion, app.lotse_engine.current_state, app.lotse_engine.last_delta)
