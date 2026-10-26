"""Overlap independent stages and always join/account for the admitted background job."""
def run_with_background(foreground, background, commit, executor):
    future=executor.submit(background)
    foreground_error=None
    try:
        return foreground()
    except BaseException as error:
        foreground_error=error
        raise
    finally:
        try:result=future.result()
        except BaseException as error:
            commit(None,error)
            if foreground_error is None:raise
        else:commit(result,None)
